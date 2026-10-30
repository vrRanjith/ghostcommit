import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_user
from app.models import User
from app.ratelimit import auth_limit, write_limit
from app.security import encrypt
from app.services.github import GitHubClient, exchange_code_for_token

router = APIRouter()
settings = get_settings()

SCOPES = "read:user user:email repo"


def _redirect_uri() -> str:
    return f"{settings.app_url}/auth/github/callback"


@router.get("/auth/github/login", dependencies=[Depends(auth_limit)])
async def login(request: Request) -> RedirectResponse:
    # Random per-login value; GitHub echoes it back and we compare (CSRF protection).
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    query = urlencode(
        {"client_id": settings.github_client_id, "redirect_uri": _redirect_uri(), "scope": SCOPES, "state": state}
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")


@router.get("/auth/github/callback", dependencies=[Depends(auth_limit)])
async def callback(
    request: Request,
    code: str = Query(max_length=100),
    state: str = Query(max_length=100),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    expected = request.session.pop("oauth_state", None)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token = await exchange_code_for_token(
        settings.github_client_id, settings.github_client_secret, code, _redirect_uri()
    )
    async with GitHubClient(token) as gh:
        gh_user = await gh.get_user()
        email = await gh.get_primary_email()

    # Upsert: first login creates the user, later logins refresh profile + token.
    user = await session.scalar(select(User).where(User.github_id == gh_user["id"]))
    if user is None:
        user = User(github_id=gh_user["id"], stall_days=settings.stall_days)
        session.add(user)
    user.login = gh_user["login"]
    user.name = gh_user.get("name")
    user.avatar_url = gh_user.get("avatar_url")
    user.email = email
    user.access_token_enc = encrypt(token)
    await session.commit()

    # Start from a clean session on login so nothing planted before authentication carries over.
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(settings.app_url + "/")


@router.post("/auth/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


class SettingsIn(BaseModel):
    notify_email: bool | None = None
    stall_days: int | None = Field(default=None, ge=1, le=90)


def me_out(user: User) -> dict:
    return {
        "login": user.login,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "email": user.email,
        "notify_email": user.notify_email,
        "stall_days": user.stall_days,
    }


@router.get("/api/me")
async def me(user: User = Depends(current_user)) -> dict:
    return me_out(user)


@router.patch("/api/me", dependencies=[Depends(write_limit)])
async def update_settings(
    body: SettingsIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    # exclude_unset: only change the fields the client actually sent.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    return me_out(user)
