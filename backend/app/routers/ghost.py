from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_user, owned_repo
from app.models import ChatMessage, ParkingNote, Repo, User
from app.ratelimit import chat_limit, note_limit, sync_limit
from app.routers.repos import repo_out
from app.security import decrypt
from app.services.backboard import BackboardClient
from app.services.github import GitHubClient
from app.services.sync import sync_repo

router = APIRouter(prefix="/api/repos/{repo_id}")


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.get("")
async def get_repo(repo: Repo = Depends(owned_repo)) -> dict:
    return repo_out(repo)


@router.post("/sync", dependencies=[Depends(sync_limit)])
async def sync(
    repo: Repo = Depends(owned_repo), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    bb = BackboardClient()
    try:
        async with GitHubClient(decrypt(user.access_token_enc)) as gh:
            result = await sync_repo(repo, gh, bb)
    finally:
        await bb.aclose()
    await session.commit()
    return result


@router.get("/notes")
async def list_notes(repo: Repo = Depends(owned_repo), session: AsyncSession = Depends(get_session)) -> list[dict]:
    notes = await session.scalars(
        select(ParkingNote).where(ParkingNote.repo_id == repo.id).order_by(ParkingNote.created_at.desc())
    )
    return [{"id": n.id, "content": n.content, "created_at": n.created_at} for n in notes]


@router.post("/notes", status_code=201, dependencies=[Depends(note_limit)])
async def add_note(body: NoteIn, repo: Repo = Depends(owned_repo), session: AsyncSession = Depends(get_session)) -> dict:
    bb = BackboardClient()
    try:
        result = await bb.add_memory(
            repo.backboard_assistant_id,
            f"Parking note ({date.today():%b %d, %Y}), written by the developer when they stopped: {body.content}",
            metadata={"type": "parking_note"},
        )
    finally:
        await bb.aclose()
    note = ParkingNote(repo_id=repo.id, content=body.content, backboard_memory_id=result.get("memory_id"))
    session.add(note)
    await session.commit()
    return {"id": note.id, "content": note.content, "created_at": note.created_at}


@router.get("/messages")
async def list_messages(repo: Repo = Depends(owned_repo), session: AsyncSession = Depends(get_session)) -> list[dict]:
    msgs = await session.scalars(
        select(ChatMessage).where(ChatMessage.repo_id == repo.id).order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return [message_out(m) for m in msgs]


@router.post("/chat", dependencies=[Depends(chat_limit)])
async def chat(
    body: ChatIn,
    repo: Repo = Depends(owned_repo),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    bb = BackboardClient()
    try:
        # Never let an empty ghost talk: with no memories the model fills the gap with fiction.
        if repo.last_synced_at is None:
            async with GitHubClient(decrypt(user.access_token_enc)) as gh:
                await sync_repo(repo, gh, bb)
            await session.commit()
        reply = await bb.send_message(repo.backboard_thread_id, grounded(body.message, repo), memory="Readonly")
    finally:
        await bb.aclose()
    # Save only after the ghost answered, so a failed call leaves no orphan question.
    user_msg = ChatMessage(repo_id=repo.id, role="user", content=body.message)
    ghost_msg = ChatMessage(repo_id=repo.id, role="ghost", content=reply)
    session.add_all([user_msg, ghost_msg])
    await session.commit()
    return message_out(ghost_msg)


def grounded(message: str, repo: Repo) -> str:
    """Wrap the user's message with facts and rules the model must follow.

    Rules next to the question are followed far more reliably than the system prompt alone,
    and they also reach ghosts whose system prompt is already fixed in Backboard.
    """
    last_commit = f"{repo.last_commit_at:%Y-%m-%d}" if repo.last_commit_at else "none (the repository has no commits)"
    return f"""[Today is {date.today():%Y-%m-%d}. Last commit: {last_commit}.]
[Rules: state only facts, dates, files and notes that appear in your memories or in this header.
Quote a parking note only word for word; never invent one. If you don't remember something,
say "that memory is faint" instead of guessing. Reply in plain text: no markdown, no asterisks.]

{message}"""


def message_out(m: ChatMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
