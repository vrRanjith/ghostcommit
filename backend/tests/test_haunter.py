"""The haunter run as a whole: one broken repo must never take down the others."""

from datetime import datetime, timezone

from sqlalchemy import func, select

from app import haunter
from app.db import SessionLocal
from app.models import Haunting, Repo
from app.services.github import GitHubError
from tests.conftest import FakeBackboard, FakeGitHub, commit, make_repo, make_user

OLD = "2024-01-01T00:00:00Z"


class PerRepoGitHub(FakeGitHub):
    """Fails for repos whose name contains 'broken', like a deleted repo or a GitHub outage."""

    async def list_commits(self, full_name, per_page=30):
        if "broken" in full_name:
            raise GitHubError(f"GET /repos/{full_name}/commits -> 500: boom", 500)
        return self.commits


async def test_one_failing_repo_does_not_crash_the_run(client, monkeypatch):
    user = await make_user()
    await make_repo(user, name="broken", github_id=1)  # fails first...
    healthy = await make_repo(user, name="healthy", github_id=2)  # ...this one must still be haunted
    old = commit("c1", OLD)
    monkeypatch.setattr(haunter, "GitHubClient", lambda token: PerRepoGitHub(commits=[old], details={"c1": old}))
    monkeypatch.setattr(haunter, "BackboardClient", lambda: FakeBackboard(reply="Come back to me."))

    summary = await haunter._run(force=False)

    assert summary == {"checked": 2, "haunted": 1, "failed": 1}
    async with SessionLocal() as s:
        hauntings = (await s.scalars(select(Haunting))).all()
        assert [h.repo_id for h in hauntings] == [healthy.id]
        assert (await s.get(Repo, healthy.id)).last_haunted_at is not None


async def test_run_with_no_repos_is_a_noop(client, monkeypatch):
    monkeypatch.setattr(haunter, "BackboardClient", lambda: FakeBackboard())
    assert await haunter._run(force=False) == {"checked": 0, "haunted": 0, "failed": 0}
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count()).select_from(Haunting)) == 0


def test_now_is_timezone_aware():
    # is_due compares against stored aware datetimes; a naive "now" would raise TypeError.
    assert datetime.now(timezone.utc).tzinfo is not None
