"""sync_repo: turning commits into exactly one distilled memory, and only when needed."""

from app.models import Repo
from app.services.sync import sync_repo
from tests.conftest import FakeBackboard, FakeGitHub, commit


def _repo(**kw) -> Repo:
    return Repo(full_name="alice/proj", backboard_assistant_id="asst-1", **kw)


async def test_first_sync_writes_one_memory_with_readme():
    commits = [commit("c2", "2026-02-02T00:00:00Z", "add chat"), commit("c1", "2026-02-01T00:00:00Z", "init")]
    gh = FakeGitHub(commits=commits, details={c["sha"]: c for c in commits}, readme="# Proj\nA chat app")
    bb = FakeBackboard(reply="Work session 2026-02-01 to 2026-02-02: built chat.")
    repo = _repo()

    result = await sync_repo(repo, gh, bb)

    assert result["new_commits"] == 2
    assert len(bb.calls_named("add_memory")) == 1  # one memory per sync, not per commit
    prompt = bb.calls_named("send_message")[0][1]
    assert "README" in prompt and "A chat app" in prompt
    assert bb.calls_named("send_message")[0][2] == "off"  # summarizing must not read/write memory
    assert repo.last_synced_sha == "c2"
    assert repo.last_commit_at.year == 2026


async def test_only_new_commits_since_last_sync_are_summarized():
    commits = [commit("c3", "2026-03-03T00:00:00Z", "fix"), commit("c2", "2026-03-02T00:00:00Z"), commit("c1", "2026-03-01T00:00:00Z")]
    gh = FakeGitHub(commits=commits, details={c["sha"]: c for c in commits})
    bb = FakeBackboard()
    repo = _repo(last_synced_sha="c2")

    result = await sync_repo(repo, gh, bb)

    assert result["new_commits"] == 1
    prompt = bb.calls_named("send_message")[0][1]
    assert "c3"[:7] in prompt and "README" not in prompt  # README only on first sync


async def test_no_new_commits_costs_nothing():
    commits = [commit("c1", "2026-03-01T00:00:00Z")]
    gh = FakeGitHub(commits=commits, details={"c1": commits[0]})
    bb = FakeBackboard()
    repo = _repo(last_synced_sha="c1")

    result = await sync_repo(repo, gh, bb)

    assert result == {"new_commits": 0, "memory": None}
    assert bb.calls == []  # no LLM call, no memory write
    assert repo.last_synced_at is not None


async def test_empty_repository_is_synced_without_inventing_anything():
    gh = FakeGitHub(commits=[])
    bb = FakeBackboard()
    repo = _repo()

    result = await sync_repo(repo, gh, bb)

    assert result["new_commits"] == 0
    assert repo.last_synced_at is not None and repo.last_commit_at is None
    assert bb.calls == []
