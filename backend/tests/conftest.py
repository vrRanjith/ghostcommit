"""Test setup: an isolated SQLite database, safe settings, and fakes for GitHub/Backboard.

The environment is overridden *before* the app is imported, so tests never see real keys
and can never reach the real GitHub or Backboard.
"""

import base64
import json
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="ghostcommit-tests-"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{_tmp / 'test.db'}",
        "APP_URL": "http://testserver",
        "SESSION_SECRET": "test-session-secret-" + "x" * 32,
        "TOKEN_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"k" * 32).decode(),
        "GITHUB_CLIENT_ID": "test-client-id",
        "GITHUB_CLIENT_SECRET": "test-client-secret",
        "BACKBOARD_API_KEY": "test-backboard-key",
        "RESEND_API_KEY": "",
        "SMTP_HOST": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from itsdangerous import TimestampSigner  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Repo, User  # noqa: E402
from app.ratelimit import ALL_LIMITS  # noqa: E402
from app.security import encrypt  # noqa: E402
from app.services.backboard import BackboardError  # noqa: E402
from app.services.github import GitHubError  # noqa: E402

ORIGIN = "http://testserver"
# Python's cookie jar stores cookies for dot-less hosts under "<host>.local"; planting ours
# there too means server Set-Cookie updates (like logout's expiry) replace it, as in a browser.
COOKIE_DOMAIN = "testserver.local"


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    for limit in ALL_LIMITS:
        limit.window.reset()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as c:
        yield c
    await engine.dispose()


def login_as(client: httpx.AsyncClient, user_id: int, secret: str | None = None) -> None:
    """Build the same signed session cookie Starlette's SessionMiddleware would issue."""
    payload = base64.b64encode(json.dumps({"user_id": user_id}).encode())
    signer = TimestampSigner(secret or os.environ["SESSION_SECRET"])
    client.cookies.set("session", signer.sign(payload).decode(), domain=COOKIE_DOMAIN)


async def make_user(github_id: int = 1, login: str = "alice") -> User:
    async with SessionLocal() as s:
        user = User(github_id=github_id, login=login, access_token_enc=encrypt(f"gho_{login}"), stall_days=7)
        s.add(user)
        await s.commit()
        return user


async def make_repo(user: User, name: str = "proj", github_id: int = 100) -> Repo:
    async with SessionLocal() as s:
        repo = Repo(
            user_id=user.id,
            github_id=github_id,
            full_name=f"{user.login}/{name}",
            backboard_assistant_id="asst-1",
            backboard_thread_id="thread-1",
        )
        s.add(repo)
        await s.commit()
        return repo


class FakeBackboard:
    """Records every call; never touches the network."""

    def __init__(self, reply: str = "I remember you.", fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.calls: list[tuple] = []

    async def _maybe_fail(self) -> None:
        if self.fail:
            raise BackboardError("POST /x -> 500: internal stack trace with secrets")

    async def create_assistant(self, name, system_prompt):
        await self._maybe_fail()
        self.calls.append(("create_assistant", name))
        return "asst-new"

    async def create_thread(self, assistant_id):
        await self._maybe_fail()
        self.calls.append(("create_thread", assistant_id))
        return f"thread-{len(self.calls)}"

    async def add_memory(self, assistant_id, content, metadata=None):
        await self._maybe_fail()
        self.calls.append(("add_memory", content))
        return {"memory_id": "mem-1", "success": True}

    async def send_message(self, thread_id, content, memory="Auto"):
        await self._maybe_fail()
        self.calls.append(("send_message", content, memory))
        return self.reply

    async def delete_assistant(self, assistant_id):
        await self._maybe_fail()
        self.calls.append(("delete_assistant", assistant_id))

    async def aclose(self):
        pass

    def calls_named(self, name: str) -> list[tuple]:
        return [c for c in self.calls if c[0] == name]


class FakeGitHub:
    """Async context manager standing in for GitHubClient."""

    def __init__(
        self,
        *,
        user: dict | None = None,
        repo: dict | None = None,
        commits: list[dict] | None = None,
        details: dict[str, dict] | None = None,
        readme: str | None = None,
        error: GitHubError | None = None,
    ) -> None:
        self.user = user or {"id": 1, "login": "alice", "name": "Alice", "avatar_url": None}
        self.repo = repo
        self.commits = commits or []
        self.details = details or {}
        self.readme = readme
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    def _check(self) -> None:
        if self.error:
            raise self.error

    async def get_user(self):
        self._check()
        return self.user

    async def get_primary_email(self):
        return "alice@example.com"

    async def list_repos(self):
        self._check()
        return [self.repo] if self.repo else []

    async def get_repo(self, full_name):
        self._check()
        return self.repo

    async def list_commits(self, full_name, per_page=30):
        self._check()
        return self.commits

    async def get_commit(self, full_name, sha):
        return self.details[sha]

    async def get_readme(self, full_name):
        return self.readme


def commit(sha: str, date: str, message: str = "work", files: list[dict] | None = None) -> dict:
    return {"sha": sha, "commit": {"message": message, "committer": {"date": date}}, "files": files or []}


@pytest.fixture
def fake_bb(monkeypatch) -> FakeBackboard:
    bb = FakeBackboard()
    for module in ("app.routers.repos", "app.routers.ghost"):
        monkeypatch.setattr(f"{module}.BackboardClient", lambda: bb)
    return bb


@pytest.fixture
def fake_gh(monkeypatch) -> FakeGitHub:
    gh = FakeGitHub()
    for module in ("app.routers.repos", "app.routers.ghost", "app.routers.auth"):
        monkeypatch.setattr(f"{module}.GitHubClient", lambda token: gh)
    return gh
