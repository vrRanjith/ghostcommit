from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    login: Mapped[str] = mapped_column(String(100))
    name: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    access_token_enc: Mapped[str] = mapped_column(Text)  # Fernet-encrypted GitHub token
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    stall_days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repos: Mapped[list["Repo"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Repo(Base):
    """A repo the user is tracking. Each repo is its own Backboard assistant (= its ghost)."""

    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    github_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(String(200))  # "owner/name"
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    backboard_assistant_id: Mapped[str | None] = mapped_column(String(64))
    backboard_thread_id: Mapped[str | None] = mapped_column(String(64))

    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_sha: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_haunted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="repos")
    notes: Mapped[list["ParkingNote"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    hauntings: Mapped[list["Haunting"]] = relationship(back_populates="repo", cascade="all, delete-orphan")


class ParkingNote(Base):
    """A one-liner the user leaves when they stop working ("stuck on OAuth redirect")."""

    __tablename__ = "parking_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    backboard_memory_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repo: Mapped[Repo] = relationship(back_populates="notes")


class ChatMessage(Base):
    """The séance transcript, so a page reload doesn't wipe the conversation."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # "user" | "ghost"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Haunting(Base):
    """A message the ghost sends when a repo has stalled."""

    __tablename__ = "hauntings"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repo: Mapped[Repo] = relationship(back_populates="hauntings")
