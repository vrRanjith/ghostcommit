"""HTTP-level tests against the real app (SQLite DB, fake GitHub/Backboard).

Most tests here play an attacker and assert the attack fails.
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import ChatMessage, Haunting, ParkingNote, Repo, User
from app.security import decrypt
from app.services.github import GitHubError
from tests.conftest import COOKIE_DOMAIN, ORIGIN, login_as, make_repo, make_user

JSON = {"Origin": ORIGIN}  # what our own frontend sends on writes


# ---------- authentication & sessions ----------

async def test_api_requires_login(client):
    for path in ["/api/me", "/api/repos", "/api/hauntings", "/api/github/repos"]:
        assert (await client.get(path)).status_code == 401


async def test_forged_session_cookie_is_rejected(client):
    user = await make_user()
    login_as(client, user.id, secret="attacker-guessed-secret-" + "z" * 32)
    assert (await client.get("/api/me")).status_code == 401


async def test_tampered_session_cookie_is_rejected(client):
    user = await make_user()
    login_as(client, user.id)
    value = client.cookies["session"]
    client.cookies.set("session", value[:-3] + ("AAA" if not value.endswith("AAA") else "BBB"), domain=COOKIE_DOMAIN)
    assert (await client.get("/api/me")).status_code == 401


async def test_valid_session_works_and_logout_clears_it(client):
    user = await make_user()
    login_as(client, user.id)
    assert (await client.get("/api/me")).json()["login"] == "alice"
    assert (await client.post("/auth/logout", headers=JSON)).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


# ---------- OAuth flow ----------

async def test_login_redirects_to_github_with_random_state(client):
    r1 = await client.get("/auth/github/login")
    client.cookies.clear()
    r2 = await client.get("/auth/github/login")
    assert r1.status_code == 307
    q1, q2 = parse_qs(urlsplit(r1.headers["location"]).query), parse_qs(urlsplit(r2.headers["location"]).query)
    assert urlsplit(r1.headers["location"]).netloc == "github.com"
    assert q1["client_id"] == ["test-client-id"]
    assert q1["redirect_uri"] == [f"{ORIGIN}/auth/github/callback"]
    assert q1["state"] != q2["state"] and len(q1["state"][0]) >= 32


async def test_callback_rejects_wrong_or_missing_state(client, monkeypatch):
    exchanged = []
    monkeypatch.setattr("app.routers.auth.exchange_code_for_token", lambda *a: exchanged.append(a))
    # no login started: no state in session (login CSRF attempt)
    assert (await client.get("/auth/github/callback?code=c&state=forged")).status_code == 400
    # login started, but attacker supplies a different state
    await client.get("/auth/github/login")
    assert (await client.get("/auth/github/callback?code=c&state=forged")).status_code == 400
    assert exchanged == []  # the code was never even exchanged


async def test_callback_logs_in_and_stores_token_encrypted(client, monkeypatch, fake_gh):
    async def exchange(*args):
        return "gho_real_token"

    monkeypatch.setattr("app.routers.auth.exchange_code_for_token", exchange)
    location = (await client.get("/auth/github/login")).headers["location"]
    state = parse_qs(urlsplit(location).query)["state"][0]

    r = await client.get(f"/auth/github/callback?code=abc&state={state}")

    assert r.status_code == 307 and r.headers["location"] == f"{ORIGIN}/"
    assert (await client.get("/api/me")).json()["login"] == "alice"
    async with SessionLocal() as s:
        user = await s.scalar(select(User))
    assert "gho_real_token" not in user.access_token_enc
    assert decrypt(user.access_token_enc) == "gho_real_token"
    # state is single-use: replaying the same callback fails
    assert (await client.get(f"/auth/github/callback?code=abc&state={state}")).status_code == 400


# ---------- authorization (IDOR) ----------

async def test_users_cannot_touch_each_others_ghosts(client, fake_bb, fake_gh):
    alice = await make_user(1, "alice")
    bob = await make_user(2, "bob")
    alices_repo = await make_repo(alice)
    login_as(client, bob.id)
    rid = alices_repo.id

    assert (await client.get("/api/repos")).json() == []
    assert (await client.get(f"/api/repos/{rid}")).status_code == 404
    assert (await client.get(f"/api/repos/{rid}/messages")).status_code == 404
    assert (await client.get(f"/api/repos/{rid}/notes")).status_code == 404
    assert (await client.post(f"/api/repos/{rid}/chat", json={"message": "hi"}, headers=JSON)).status_code == 404
    assert (await client.post(f"/api/repos/{rid}/notes", json={"content": "x"}, headers=JSON)).status_code == 404
    assert (await client.post(f"/api/repos/{rid}/sync", headers=JSON)).status_code == 404
    assert (await client.delete(f"/api/repos/{rid}", headers=JSON)).status_code == 404
    assert fake_bb.calls == []  # nothing reached Backboard on Alice's behalf
    async with SessionLocal() as s:
        assert await s.get(Repo, rid) is not None


async def test_users_cannot_read_or_mark_each_others_hauntings(client):
    alice = await make_user(1, "alice")
    bob = await make_user(2, "bob")
    repo = await make_repo(alice)
    async with SessionLocal() as s:
        s.add(Haunting(repo_id=repo.id, message="boo"))
        await s.commit()
    login_as(client, bob.id)
    assert (await client.get("/api/hauntings")).json() == []
    assert (await client.post("/api/hauntings/1/read", headers=JSON)).status_code == 404


async def test_cannot_summon_a_repo_you_do_not_own(client, fake_bb, fake_gh):
    user = await make_user(1, "alice")
    fake_gh.repo = {"id": 9, "full_name": "torvalds/linux", "owner": {"id": 999}, "default_branch": "master", "private": False}
    login_as(client, user.id)
    r = await client.post("/api/repos", json={"full_name": "torvalds/linux"}, headers=JSON)
    assert r.status_code == 403
    assert fake_bb.calls == []


# ---------- CSRF ----------

async def test_cross_site_writes_are_blocked(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    url = f"/api/repos/{repo.id}/notes"
    evil = {"Origin": "https://evil.example"}
    no_origin_cross_site = {"Sec-Fetch-Site": "cross-site"}

    assert (await client.post(url, json={"content": "x"}, headers=evil)).status_code == 403
    assert (await client.post(url, json={"content": "x"}, headers=no_origin_cross_site)).status_code == 403
    assert (await client.post("/auth/logout", headers=evil)).status_code == 403
    assert fake_bb.calls == []
    # the same request from our own origin works
    assert (await client.post(url, json={"content": "x"}, headers=JSON)).status_code == 201


async def test_form_encoded_body_is_not_accepted_as_json(client):
    # Classic CSRF uses <form> posts; our endpoints only take application/json.
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    r = await client.post(f"/api/repos/{repo.id}/notes", data={"content": "x"}, headers=JSON)
    assert r.status_code == 422


# ---------- injection & input validation ----------

async def test_sql_injection_payloads_are_stored_as_plain_text(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    payload = "'); DROP TABLE users; --"
    r = await client.post(f"/api/repos/{repo.id}/notes", json={"content": payload}, headers=JSON)
    assert r.status_code == 201
    assert (await client.get(f"/api/repos/{repo.id}/notes")).json()[0]["content"] == payload
    assert (await client.get("/api/me")).status_code == 200  # users table still exists


async def test_non_integer_ids_are_rejected(client):
    user = await make_user()
    login_as(client, user.id)
    assert (await client.get("/api/repos/1%20OR%201=1")).status_code == 422


async def test_summon_rejects_path_injection(client, fake_bb, fake_gh):
    user = await make_user()
    login_as(client, user.id)
    for bad in ["../../user", "alice/proj/../../x", "alice/proj?per_page=1"]:
        r = await client.post("/api/repos", json={"full_name": bad}, headers=JSON)
        assert r.status_code == 422, bad
    assert fake_bb.calls == []


async def test_oversized_and_overlong_inputs_are_rejected(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    huge = "x" * 100_000
    assert (await client.post(f"/api/repos/{repo.id}/chat", json={"message": huge}, headers=JSON)).status_code == 413
    too_long = "x" * 2001  # under the body cap, over the field limit
    assert (await client.post(f"/api/repos/{repo.id}/chat", json={"message": too_long}, headers=JSON)).status_code == 422
    assert fake_bb.calls == []


async def test_settings_only_accept_sane_values(client):
    user = await make_user()
    login_as(client, user.id)
    for bad in [0, -1, 91, 10_000]:
        assert (await client.patch("/api/me", json={"stall_days": bad}, headers=JSON)).status_code == 422
    r = await client.patch("/api/me", json={"stall_days": 3}, headers=JSON)
    assert r.json()["stall_days"] == 3 and r.json()["notify_email"] is True  # partial update only


# ---------- abuse / DoS ----------

async def test_chat_is_rate_limited(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    async with SessionLocal() as s:
        r = await s.get(Repo, repo.id)
        r.last_synced_at = r.created_at  # already synced: chat won't trigger a sync
        await s.commit()
    login_as(client, user.id)
    url = f"/api/repos/{repo.id}/chat"
    for _ in range(20):
        assert (await client.post(url, json={"message": "hi"}, headers=JSON)).status_code == 200
    r = await client.post(url, json={"message": "hi"}, headers=JSON)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    assert len(fake_bb.calls_named("send_message")) == 20  # the 21st never cost anything


async def test_ghost_count_is_capped(client, fake_bb, fake_gh):
    user = await make_user()
    for i in range(25):
        await make_repo(user, name=f"p{i}", github_id=1000 + i)
    login_as(client, user.id)
    r = await client.post("/api/repos", json={"full_name": "alice/one-more"}, headers=JSON)
    assert r.status_code == 400


async def test_duplicate_summon_with_different_case_is_rejected(client, fake_bb, fake_gh):
    user = await make_user()
    await make_repo(user, name="Proj", github_id=100)
    fake_gh.repo = {"id": 100, "full_name": "alice/Proj", "owner": {"id": 1}, "default_branch": "main", "private": False}
    login_as(client, user.id)
    r = await client.post("/api/repos", json={"full_name": "ALICE/proj"}, headers=JSON)
    assert r.status_code == 409


# ---------- error handling & information leaks ----------

async def test_revoked_github_token_asks_user_to_reconnect(client, fake_gh):
    user = await make_user()
    fake_gh.error = GitHubError("GET /user/repos -> 401: Bad credentials", 401)
    login_as(client, user.id)
    r = await client.get("/api/github/repos")
    assert r.status_code == 401 and r.json()["detail"] == "github_reconnect"


async def test_upstream_errors_do_not_leak_internals(client, fake_bb, fake_gh):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)

    fake_gh.error = GitHubError("GET /x -> 500: internal db host 10.0.0.5", 500)
    r = await client.get("/api/github/repos")
    assert r.status_code == 502 and "10.0.0.5" not in r.text

    fake_bb.fail = True
    r = await client.post(f"/api/repos/{repo.id}/notes", json={"content": "x"}, headers=JSON)
    assert r.status_code == 502 and "stack trace" not in r.text


async def test_failed_chat_saves_nothing(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    async with SessionLocal() as s:
        (await s.get(Repo, repo.id)).last_synced_at = (await s.get(Repo, repo.id)).created_at
        await s.commit()
    fake_bb.fail = True
    login_as(client, user.id)
    assert (await client.post(f"/api/repos/{repo.id}/chat", json={"message": "hi"}, headers=JSON)).status_code == 502
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count()).select_from(ChatMessage)) == 0


# ---------- dismissing hauntings ----------

async def _haunting(repo, message="boo") -> int:
    async with SessionLocal() as s:
        h = Haunting(repo_id=repo.id, message=message)
        s.add(h)
        await s.commit()
        return h.id


async def test_dismiss_one_haunting_keeps_the_cooldown(client):
    user = await make_user()
    repo = await make_repo(user)
    async with SessionLocal() as s:
        r = await s.get(Repo, repo.id)
        r.last_haunted_at = r.created_at
        await s.commit()
    keep, gone = await _haunting(repo, "keep"), await _haunting(repo, "gone")
    login_as(client, user.id)

    assert (await client.delete(f"/api/hauntings/{gone}", headers=JSON)).status_code == 204

    assert [h["id"] for h in (await client.get("/api/hauntings")).json()] == [keep]
    async with SessionLocal() as s:
        assert (await s.get(Repo, repo.id)).last_haunted_at is not None  # no immediate re-haunt


async def test_dismiss_all_only_clears_your_own(client):
    alice, bob = await make_user(1, "alice"), await make_user(2, "bob")
    alices_repo, bobs_repo = await make_repo(alice), await make_repo(bob, github_id=200)
    await _haunting(alices_repo)
    await _haunting(alices_repo)
    bobs = await _haunting(bobs_repo)
    login_as(client, alice.id)

    assert (await client.delete("/api/hauntings", headers=JSON)).status_code == 204

    assert (await client.get("/api/hauntings")).json() == []
    async with SessionLocal() as s:
        assert await s.get(Haunting, bobs) is not None


async def test_cannot_dismiss_someone_elses_haunting(client):
    alice, bob = await make_user(1, "alice"), await make_user(2, "bob")
    hid = await _haunting(await make_repo(alice))
    login_as(client, bob.id)
    assert (await client.delete(f"/api/hauntings/{hid}", headers=JSON)).status_code == 404
    assert (await client.delete(f"/api/hauntings/{hid}", headers={"Origin": "https://evil.example"})).status_code == 403
    async with SessionLocal() as s:
        assert await s.get(Haunting, hid) is not None


# ---------- scheduled haunting trigger ----------

HAUNT_SECRET = "h" * 40


@pytest.fixture
def haunter_spy(monkeypatch):
    calls = []

    async def fake_run(force):
        calls.append(force)
        return {"checked": 2, "haunted": 1}

    monkeypatch.setattr("app.haunter.run", fake_run)
    return calls


async def test_haunt_trigger_is_disabled_without_a_secret(client, haunter_spy, monkeypatch):
    monkeypatch.setattr(get_settings(), "haunt_secret", "")
    r = await client.post("/internal/haunt", headers={"Authorization": "Bearer "})
    assert r.status_code == 404
    assert haunter_spy == []


async def test_haunt_trigger_rejects_missing_or_wrong_token(client, haunter_spy, monkeypatch):
    monkeypatch.setattr(get_settings(), "haunt_secret", HAUNT_SECRET)
    for headers in [{}, {"Authorization": "Bearer wrong"}, {"Authorization": HAUNT_SECRET}]:
        assert (await client.post("/internal/haunt", headers=headers)).status_code == 401
    assert haunter_spy == []


async def test_haunt_trigger_runs_with_the_right_token(client, haunter_spy, monkeypatch):
    monkeypatch.setattr(get_settings(), "haunt_secret", HAUNT_SECRET)
    r = await client.post("/internal/haunt", headers={"Authorization": f"Bearer {HAUNT_SECRET}"})
    assert r.status_code == 200
    assert r.json() == {"checked": 2, "haunted": 1}
    assert haunter_spy == [False]  # never forced: the cooldown still applies


async def test_haunt_trigger_is_rate_limited(client, haunter_spy, monkeypatch):
    monkeypatch.setattr(get_settings(), "haunt_secret", HAUNT_SECRET)
    auth = {"Authorization": f"Bearer {HAUNT_SECRET}"}
    for _ in range(5):
        assert (await client.post("/internal/haunt", headers=auth)).status_code == 200
    assert (await client.post("/internal/haunt", headers=auth)).status_code == 429


async def test_haunter_never_runs_twice_at_once():
    from app import haunter

    async with haunter._running:  # simulate a run already in progress
        assert await haunter.run(force=False) == {"checked": 0, "haunted": 0, "skipped_busy": 1}


# ---------- core behaviour ----------

async def test_chat_is_grounded_readonly_and_persisted(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    async with SessionLocal() as s:
        (await s.get(Repo, repo.id)).last_synced_at = (await s.get(Repo, repo.id)).created_at
        await s.commit()
    fake_bb.reply = "You left me mid-refactor."
    login_as(client, user.id)

    r = await client.post(f"/api/repos/{repo.id}/chat", json={"message": "Where was I?"}, headers=JSON)

    assert r.json()["role"] == "ghost" and r.json()["content"] == "You left me mid-refactor."
    _, prompt, memory = fake_bb.calls_named("send_message")[0]
    assert memory == "Readonly"  # chat never writes memories (cost control)
    assert "never invent one" in prompt and prompt.endswith("Where was I?")
    history = (await client.get(f"/api/repos/{repo.id}/messages")).json()
    assert [m["role"] for m in history] == ["user", "ghost"]


async def test_chat_with_unsynced_ghost_syncs_first(client, fake_bb, fake_gh):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    await client.post(f"/api/repos/{repo.id}/chat", json={"message": "hi"}, headers=JSON)
    async with SessionLocal() as s:
        assert (await s.get(Repo, repo.id)).last_synced_at is not None


async def test_parking_note_becomes_a_memory(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    await client.post(f"/api/repos/{repo.id}/notes", json={"content": "stuck on OAuth"}, headers=JSON)
    assert "stuck on OAuth" in fake_bb.calls_named("add_memory")[0][1]
    async with SessionLocal() as s:
        note = await s.scalar(select(ParkingNote))
    assert note.backboard_memory_id == "mem-1"


async def test_banish_erases_backboard_memories_too(client, fake_bb):
    user = await make_user()
    repo = await make_repo(user)
    login_as(client, user.id)
    assert (await client.delete(f"/api/repos/{repo.id}", headers=JSON)).status_code == 204
    assert fake_bb.calls_named("delete_assistant") == [("delete_assistant", "asst-1")]
    async with SessionLocal() as s:
        assert await s.get(Repo, repo.id) is None


async def test_security_headers_are_set(client):
    r = await client.get("/api/health")
    assert r.json() == {"status": "ok", "db": "ok"}
    h = r.headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert "script-src 'self'" in h["Content-Security-Policy"]
    assert h["Cache-Control"] == "no-store"


async def test_session_cookie_is_httponly_and_samesite(client):
    r = await client.get("/auth/github/login")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
