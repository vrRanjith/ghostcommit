from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Repo, User


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    user_id = request.session.get("user_id")
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


async def owned_repo(
    repo_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Repo:
    repo = await session.get(Repo, repo_id)
    # 404 rather than 403: don't reveal that someone else's repo id exists.
    if repo is None or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
