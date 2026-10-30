import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_user, owned_repo
from app.models import Repo, User
from app.ratelimit import github_list_limit, summon_limit, write_limit
from app.security import decrypt
from app.services.backboard import BackboardClient, BackboardError
from app.services.ghost import ghost_system_prompt
from app.services.github import GitHubClient

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


MAX_GHOSTS_PER_USER = 25

# GitHub rules: owner is 1-39 alphanumerics/hyphens; repo name 1-100 of [A-Za-z0-9._-].
FULL_NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")


class SummonRequest(BaseModel):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def valid_full_name(cls, v: str) -> str:
        # Strict allow-list: the value becomes part of a GitHub API URL path, so anything like
        # "../" or "?" could otherwise reshape the request.
        if not FULL_NAME_RE.fullmatch(v) or v.split("/")[1] in (".", ".."):
            raise ValueError("must look like owner/repo")
        return v


def repo_out(repo: Repo) -> dict:
    return {
        "id": repo.id,
        "full_name": repo.full_name,
        "is_private": repo.is_private,
        "last_commit_at": repo.last_commit_at,
        "last_synced_at": repo.last_synced_at,
        "last_haunted_at": repo.last_haunted_at,
    }


@router.get("/github/repos", dependencies=[Depends(github_list_limit)])
async def github_repos(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    """The user's GitHub repos, for the 'summon a ghost' picker."""
    async with GitHubClient(decrypt(user.access_token_enc)) as gh:
        repos = await gh.list_repos()
    tracked = set(await session.scalars(select(Repo.full_name).where(Repo.user_id == user.id)))
    return [
        {
            "full_name": r["full_name"],
            "description": r["description"],
            "private": r["private"],
            "pushed_at": r["pushed_at"],
            "tracked": r["full_name"] in tracked,
        }
        for r in repos
    ]


@router.get("/repos")
async def list_tracked(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    repos = await session.scalars(select(Repo).where(Repo.user_id == user.id).order_by(Repo.created_at.desc()))
    return [repo_out(r) for r in repos]


@router.post("/repos", status_code=201, dependencies=[Depends(summon_limit)])
async def summon(
    body: SummonRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    """Start tracking a repo: create its ghost (a Backboard assistant) and a chat thread."""
    count = await session.scalar(select(func.count()).select_from(Repo).where(Repo.user_id == user.id))
    if count >= MAX_GHOSTS_PER_USER:
        raise HTTPException(status_code=400, detail=f"You can haunt at most {MAX_GHOSTS_PER_USER} repos")

    async with GitHubClient(decrypt(user.access_token_enc)) as gh:
        gh_repo = await gh.get_repo(body.full_name)
    # Enforce on the server what the picker shows: only your own repos (the API, not the UI,
    # is what an attacker would call).
    if gh_repo["owner"]["id"] != user.github_id:
        raise HTTPException(status_code=403, detail="You can only summon ghosts for repos you own")
    # Compare GitHub's stable numeric id, not the name: "a/B" and "A/b" are the same repo.
    existing = await session.scalar(select(Repo).where(Repo.user_id == user.id, Repo.github_id == gh_repo["id"]))
    if existing:
        raise HTTPException(status_code=409, detail="This repo already has a ghost")

    bb = BackboardClient()
    try:
        assistant_id = await bb.create_assistant(f"ghost:{gh_repo['full_name']}", ghost_system_prompt(gh_repo["full_name"]))
        thread_id = await bb.create_thread(assistant_id)
    finally:
        await bb.aclose()

    repo = Repo(
        user_id=user.id,
        github_id=gh_repo["id"],
        full_name=gh_repo["full_name"],
        default_branch=gh_repo["default_branch"],
        is_private=gh_repo["private"],
        backboard_assistant_id=assistant_id,
        backboard_thread_id=thread_id,
    )
    session.add(repo)
    await session.commit()
    return repo_out(repo)


@router.delete("/repos/{repo_id}", status_code=204, dependencies=[Depends(write_limit)])
async def banish(repo: Repo = Depends(owned_repo), session: AsyncSession = Depends(get_session)) -> None:
    # Erase the ghost's memories too, not just our row; otherwise they linger orphaned in Backboard.
    if repo.backboard_assistant_id:
        bb = BackboardClient()
        try:
            await bb.delete_assistant(repo.backboard_assistant_id)
        except BackboardError:
            log.warning("could not delete Backboard assistant %s", repo.backboard_assistant_id)
        finally:
            await bb.aclose()
    await session.delete(repo)
    await session.commit()
