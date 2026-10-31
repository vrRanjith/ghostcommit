from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_user
from app.models import Haunting, Repo, User
from app.ratelimit import write_limit

router = APIRouter(prefix="/api/hauntings")


@router.get("")
async def list_hauntings(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = await session.execute(
        select(Haunting, Repo.full_name)
        .join(Repo)
        .where(Repo.user_id == user.id)
        .order_by(Haunting.created_at.desc())
        .limit(50)
    )
    return [
        {
            "id": h.id,
            "repo_id": h.repo_id,
            "repo": full_name,
            "message": h.message,
            "emailed": h.emailed,
            "read": h.read_at is not None,
            "created_at": h.created_at,
        }
        for h, full_name in rows
    ]


@router.post("/{haunting_id}/read", status_code=204, dependencies=[Depends(write_limit)])
async def mark_read(
    haunting_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> None:
    haunting = await session.scalar(
        select(Haunting).join(Repo).where(Haunting.id == haunting_id, Repo.user_id == user.id)
    )
    if haunting is None:
        raise HTTPException(status_code=404, detail="Haunting not found")
    haunting.read_at = datetime.now(timezone.utc)
    await session.commit()


# Deleting removes feed entries only. The repo's last_haunted_at (the cooldown) is untouched,
# so clearing the feed never causes an immediate re-haunt.


@router.delete("/{haunting_id}", status_code=204, dependencies=[Depends(write_limit)])
async def dismiss(
    haunting_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> None:
    haunting = await session.scalar(
        select(Haunting).join(Repo).where(Haunting.id == haunting_id, Repo.user_id == user.id)
    )
    if haunting is None:
        raise HTTPException(status_code=404, detail="Haunting not found")
    await session.delete(haunting)
    await session.commit()


@router.delete("", status_code=204, dependencies=[Depends(write_limit)])
async def dismiss_all(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> None:
    owned_repo_ids = select(Repo.id).where(Repo.user_id == user.id)
    await session.execute(delete(Haunting).where(Haunting.repo_id.in_(owned_repo_ids)))
    await session.commit()
