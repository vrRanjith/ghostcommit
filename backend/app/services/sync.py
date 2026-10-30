"""Turn new GitHub commits into one distilled 'work session' memory for a repo's ghost."""

from datetime import datetime, timezone

from app.models import Repo
from app.services.backboard import BackboardClient
from app.services.github import GitHubClient

MAX_COMMITS = 15
MAX_FILES_PER_COMMIT = 8
MAX_PATCH_CHARS = 1500
MAX_DIGEST_CHARS = 40_000
MAX_README_CHARS = 3000

# Generated / vendored files: big diffs, zero insight.
NOISE_SUFFIXES = (".lock", "-lock.json", ".min.js", ".min.css", ".map", ".svg", ".png", ".jpg", ".ico")

SUMMARY_PROMPT = """You are writing a memory for the ghost of the project "{full_name}".
Below are the developer's commits (with diff excerpts){readme_note}.

Write ONE memory of at most 150 words, plain text, starting with
"Work session {date_from} to {date_to}:". Cover:
1. what was built or changed (features, files/areas)
2. anything left unfinished, ONLY with explicit evidence: TODO/FIXME comments in added
   lines, commit messages like "wip"/"temp"/"half done", or newly commented-out code.
   If there is no such evidence, say "no unfinished work was marked".
3. the most likely next step

Be concrete (name files, functions, features). Do not invent anything not shown below.
Diffs show only changed lines, never whole files: a function that looks cut off in a diff
is NOT unfinished. Text ending in "{truncation_mark}" was shortened by the tool to save
space; never report it as broken or incomplete either.

{digest}"""


TRUNCATION_MARK = "…[truncated by GhostCommit]"


def _clip(text: str, limit: int) -> str:
    # Always mark cuts; otherwise the model mistakes our truncation for unfinished code.
    return text if len(text) <= limit else text[:limit] + TRUNCATION_MARK


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_commit(commit: dict) -> str:
    c = commit["commit"]
    lines = [f"## {c['committer']['date'][:10]} {commit['sha'][:7]}: {c['message'].strip()}"]
    files = [f for f in commit.get("files", []) if not f["filename"].endswith(NOISE_SUFFIXES)]
    for f in files[:MAX_FILES_PER_COMMIT]:
        lines.append(f"- {f['status']} {f['filename']} (+{f['additions']}/-{f['deletions']})")
        if patch := f.get("patch"):
            lines.append(_clip(patch, MAX_PATCH_CHARS))
    if len(files) > MAX_FILES_PER_COMMIT:
        lines.append(f"- ...and {len(files) - MAX_FILES_PER_COMMIT} more files")
    return "\n".join(lines)


async def sync_repo(repo: Repo, gh: GitHubClient, bb: BackboardClient) -> dict:
    """Summarize commits newer than repo.last_synced_sha into a single memory.

    Mutates `repo` (sync bookkeeping); the caller commits the DB session.
    """
    listed = await gh.list_commits(repo.full_name, per_page=MAX_COMMITS + 15)
    new = []
    for item in listed:  # newest first; stop at the last commit we already remembered
        if item["sha"] == repo.last_synced_sha:
            break
        new.append(item)

    repo.last_synced_at = datetime.now(timezone.utc)
    if listed:
        repo.last_commit_at = _parse_date(listed[0]["commit"]["committer"]["date"])
    if not new:
        return {"new_commits": 0, "memory": None}

    skipped = max(0, len(new) - MAX_COMMITS)
    new = new[:MAX_COMMITS]
    detailed = [await gh.get_commit(repo.full_name, item["sha"]) for item in reversed(new)]  # oldest first

    digest = "\n\n".join(_format_commit(c) for c in detailed)
    if skipped:
        digest = f"(plus {skipped} older commits not shown)\n\n" + digest
    readme_note = ""
    if repo.last_synced_sha is None and (readme := await gh.get_readme(repo.full_name)):
        digest = f"# README (excerpt)\n{_clip(readme, MAX_README_CHARS)}\n\n# Commits\n{digest}"
        readme_note = " and the README"
    digest = _clip(digest, MAX_DIGEST_CHARS)

    date_from = detailed[0]["commit"]["committer"]["date"][:10]
    date_to = detailed[-1]["commit"]["committer"]["date"][:10]
    prompt = SUMMARY_PROMPT.format(
        full_name=repo.full_name,
        readme_note=readme_note,
        date_from=date_from,
        date_to=date_to,
        truncation_mark=TRUNCATION_MARK,
        digest=digest,
    )

    # Scratch thread with memory off: summarizing must not read or write memories itself.
    scratch_thread = await bb.create_thread(repo.backboard_assistant_id)
    summary = (await bb.send_message(scratch_thread, prompt, memory="off")).strip()
    await bb.add_memory(
        repo.backboard_assistant_id,
        summary,
        metadata={"type": "work_session", "from": date_from, "to": date_to, "head": new[0]["sha"]},
    )

    repo.last_synced_sha = new[0]["sha"]
    return {"new_commits": len(new) + skipped, "memory": summary}
