"""Pure-logic unit tests: no HTTP, no database."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.haunter import is_due, render_email
from app.main import resolve_static
from app.models import Repo, User
from app.ratelimit import SlidingWindow
from app.routers.ghost import grounded
from app.routers.repos import SummonRequest
from app.security import decrypt, encrypt
from app.services.sync import MAX_PATCH_CHARS, TRUNCATION_MARK, _clip, _format_commit

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


# ---- encryption ----

def test_token_encryption_roundtrip_and_hides_plaintext():
    token = "gho_supersecrettoken123"
    enc = encrypt(token)
    assert token not in enc
    assert decrypt(enc) == token
    assert encrypt(token) != enc  # random IV: same input, different ciphertext


# ---- config ----

def test_short_session_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite://", session_secret="short", token_encryption_key="k")


@pytest.mark.parametrize("url", ["postgres://u:p@h/db", "postgresql://u:p@h/db"])
def test_render_database_url_gets_asyncpg_driver(url):
    s = Settings(database_url=url, session_secret="s" * 32, token_encryption_key="k")
    assert s.database_url == "postgresql+asyncpg://u:p@h/db"


# ---- path traversal ----

@pytest.mark.parametrize(
    "path", ["../secret.txt", "../../etc/passwd", "..%2Fsecret.txt", "/etc/passwd", "assets/../../secret.txt"]
)
def test_static_files_cannot_escape_static_dir(tmp_path, path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("app")
    (tmp_path / "secret.txt").write_text("secret")
    assert resolve_static(static, path) == (static / "index.html").resolve()


def test_static_files_serves_real_files(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("app")
    (static / "favicon.svg").write_text("<svg/>")
    assert resolve_static(static, "favicon.svg") == (static / "favicon.svg").resolve()
    assert resolve_static(static, "repos/1") == (static / "index.html").resolve()  # SPA route


# ---- input validation ----

@pytest.mark.parametrize("name", ["vrRanjith/Firechat-app", "a/b", "org-1/repo.name_2"])
def test_summon_accepts_valid_repo_names(name):
    assert SummonRequest(full_name=name).full_name == name


@pytest.mark.parametrize(
    "name", ["", "noslash", "a/b/c", "../etc", "a/..", "a/.", "a/b?x=1", "a/b#x", "a /b", "-" * 40 + "/b", "a/" + "b" * 101]
)
def test_summon_rejects_malformed_or_path_injecting_names(name):
    with pytest.raises(ValidationError):
        SummonRequest(full_name=name)


# ---- rate limiting ----

def test_sliding_window_blocks_after_limit_then_recovers(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("app.ratelimit.time.monotonic", lambda: clock[0])
    window = SlidingWindow(limit=3, window_seconds=60)
    for _ in range(3):
        window.hit("user")
    with pytest.raises(HTTPException) as exc:
        window.hit("user")
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"
    window.hit("someone-else")  # limits are per key
    clock[0] += 61
    window.hit("user")  # window slid past the old hits


# ---- sync helpers ----

def test_clip_marks_truncation_so_the_model_knows():
    assert _clip("short", 10) == "short"
    clipped = _clip("x" * 20, 10)
    assert clipped == "x" * 10 + TRUNCATION_MARK


def test_format_commit_skips_noise_files_and_clips_patches():
    c = {
        "sha": "abcdef123",
        "commit": {"message": "wip: auth", "committer": {"date": "2026-01-02T00:00:00Z"}},
        "files": [
            {"filename": "package-lock.json", "status": "modified", "additions": 900, "deletions": 900, "patch": "x"},
            {"filename": "src/auth.py", "status": "added", "additions": 5, "deletions": 0, "patch": "y" * 5000},
        ],
    }
    text = _format_commit(c)
    assert "package-lock.json" not in text
    assert "src/auth.py" in text
    assert "wip: auth" in text and "2026-01-02" in text
    assert TRUNCATION_MARK in text
    assert "y" * (MAX_PATCH_CHARS + 1) not in text


# ---- chat grounding ----

def test_grounded_message_carries_rules_and_facts():
    repo = Repo(last_commit_at=None)
    text = grounded("Where was I?", repo)
    assert "the repository has no commits" in text
    assert "never invent one" in text
    assert "no markdown" in text
    assert text.rstrip().endswith("Where was I?")


# ---- haunter ----

def _repo(last_commit_days_ago: int | None, last_haunted_days_ago: int | None = None) -> Repo:
    user = User(stall_days=7)
    return Repo(
        user=user,
        full_name="alice/proj",
        last_commit_at=None if last_commit_days_ago is None else NOW - timedelta(days=last_commit_days_ago),
        last_haunted_at=None if last_haunted_days_ago is None else NOW - timedelta(days=last_haunted_days_ago),
    )


@pytest.mark.parametrize(
    ("commit_ago", "haunted_ago", "force", "expected"),
    [
        (None, None, False, False),  # empty repo: nothing to haunt about
        (3, None, False, False),  # active recently
        (10, None, False, True),  # stalled, never haunted
        (10, 2, False, False),  # stalled but haunted recently: cooldown
        (30, 8, False, True),  # cooldown over
        (10, 2, True, True),  # --force skips the cooldown
    ],
)
def test_is_due(commit_ago, haunted_ago, force, expected):
    assert is_due(_repo(commit_ago, haunted_ago), NOW, force) is expected


def test_haunting_email_escapes_llm_output():
    repo = Repo(id=1, full_name="alice/proj")
    subject, text, html = render_email(repo, '<script>alert("x")</script><a href="evil">click</a>', 10)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert 'href="evil"' not in html
    assert "10 days" in subject
