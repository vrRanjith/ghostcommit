"""Daily job: find stalled repos and let their ghosts haunt the developer.

Runs once and exits (Render Cron Job). Locally: docker compose run --rm haunter [--force]
"""

import argparse
import asyncio
import html
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Haunting, Repo
from app.security import decrypt
from app.services.backboard import BackboardClient
from app.services.email import send_email
from app.services.github import GitHubClient, GitHubError
from app.services.sync import sync_repo

log = logging.getLogger("haunter")

HAUNT_PROMPT = """[Today is {today}]
The developer has not touched you for {days} days (last commit: {last_commit}).
Write a short haunting message (at most 80 words) to lure them back:
- remind them, from your memories, what they were last working on
- if they left a parking note, quote their blocker
- suggest ONE small next step they could finish in 15 minutes
Spooky and wistful in tone, but kind. Plain text, no greeting line, no sign-off."""


def is_due(repo: Repo, now: datetime, force: bool) -> bool:
    if repo.last_commit_at is None:
        return False
    stall = timedelta(days=repo.user.stall_days)
    if now - repo.last_commit_at < stall:
        return False
    # Cooldown: at most one haunting per stall window.
    return force or repo.last_haunted_at is None or now - repo.last_haunted_at >= stall


def render_email(repo: Repo, message: str, days: int) -> tuple[str, str, str]:
    url = f"{get_settings().app_url}/repos/{repo.id}"
    subject = f"👻 {repo.full_name} has been waiting for {days} days"
    text = f"{message}\n\nVisit your ghost: {url}"
    body = html.escape(message).replace("\n", "<br>")
    html_body = f"""<div style="font-family:Georgia,serif;max-width:520px;margin:auto;padding:24px;
background:#0f0f14;color:#e6e1f0;border-radius:12px">
<p style="color:#9b8cff;font-size:13px;margin:0 0 12px">👻 the ghost of {html.escape(repo.full_name)}</p>
<p style="font-size:16px;line-height:1.6">{body}</p>
<a href="{url}" style="display:inline-block;margin-top:16px;padding:10px 16px;background:#9b8cff;
color:#0f0f14;border-radius:8px;text-decoration:none">Wake me up</a></div>"""
    return subject, text, html_body


async def haunt_repo(repo: Repo, bb: BackboardClient, now: datetime, force: bool) -> Haunting | None:
    async with GitHubClient(decrypt(repo.user.access_token_enc)) as gh:
        await sync_repo(repo, gh, bb)
    if not is_due(repo, now, force):
        return None

    days = (now - repo.last_commit_at).days
    prompt = HAUNT_PROMPT.format(today=date.today(), days=days, last_commit=f"{repo.last_commit_at:%Y-%m-%d}")
    scratch_thread = await bb.create_thread(repo.backboard_assistant_id)
    message = (await bb.send_message(scratch_thread, prompt, memory="Readonly")).strip()

    haunting = Haunting(repo_id=repo.id, message=message)
    repo.last_haunted_at = now
    user = repo.user
    if user.notify_email and user.email:
        haunting.emailed = await send_email(user.email, *render_email(repo, message, days))
    return haunting


async def run(force: bool) -> None:
    await init_db()
    now = datetime.now(timezone.utc)
    bb = BackboardClient()
    async with SessionLocal() as session:
        repos = (await session.scalars(select(Repo).options(selectinload(Repo.user)))).all()
        log.info("checking %d repos", len(repos))
        for repo in repos:
            # Read before anything can fail: after rollback() the ORM object is expired, and
            # touching its attributes would trigger lazy IO, which async SQLAlchemy forbids.
            name = repo.full_name
            try:
                haunting = await haunt_repo(repo, bb, now, force)
                if haunting:
                    session.add(haunting)
                    log.info("haunted %s (emailed=%s)", name, haunting.emailed)
                await session.commit()
            except Exception as e:
                # One broken repo (revoked token, deleted repo...) must not stop the others.
                await session.rollback()
                if isinstance(e, GitHubError) and e.status_code == 401:
                    log.warning("skipped %s: GitHub token revoked, the user must log in again", name)
                else:
                    log.exception("failed on %s", name)
    await bb.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="ignore the cooldown (for demos)")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(parser.parse_args().force))
