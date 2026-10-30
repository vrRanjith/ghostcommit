# 👻 GhostCommit

**Every abandoned side project leaves a ghost. Summon it, and it tells you exactly where you left off.**

Developers start projects, get stuck, drift to something new, and forget why they stopped.
Weeks later the repo is a stranger. GhostCommit gives each repo a ghost with a memory:

- **It remembers your work.** New commits and diffs are distilled into "work session" memories.
- **It keeps your parking notes.** Leave one line when you stop ("stuck on the OAuth redirect");
  the ghost hands it back, word for word, when you return.
- **It haunts you when you stall.** A daily job finds repos gone quiet and the ghost reaches out
  (in-app and by email) with what you were doing and one small step to restart.

## How it works

```
GitHub commits ──▶ summarize (open-weight LLM) ──▶ one memory per sync ──▶ Backboard memory
                                                                              │
   "Where was I?" ──▶ grounded prompt + memory retrieval (read-only) ◀────────┘
```

- **One repo = one Backboard assistant = one ghost.** Memory is scoped per assistant, so each
  ghost remembers only its own project.
- **Cost-aware memory:** commits are summarized into a single memory per sync (not one per commit),
  chat retrieves read-only, and re-syncing with no new commits costs nothing.
- **Grounded answers:** every question carries rules (only facts from memory, quote notes verbatim,
  admit faint memories) so the ghost does not invent history.
- **Model:** Gemma 4 31B, an open-weight model, served through Backboard.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL |
| AI memory | Backboard (memory + threads), Gemma 4 31B (open-weight) via OpenRouter |
| Auth | GitHub OAuth |
| Email | Resend (production), Mailpit (local) |
| Hosting | Render: web service + PostgreSQL (Blueprint in `render.yaml`) |
| Scheduling | GitHub Actions calls a token-protected `/internal/haunt` daily |

## Run locally

Requires Docker.

```bash
cp .env.example .env        # fill in GitHub OAuth app + Backboard key; generate the two secrets
docker compose up -d        # db, api, web, mailpit
```

- App: http://localhost:5173
- Mail inbox (hauntings): http://localhost:8025
- Run the haunter once: `docker compose run --rm haunter` (add `--force` to skip the cooldown)

## Tests

```bash
docker compose exec api python -m pytest   # backend: unit, integration and security tests
cd frontend && npm test                     # frontend unit tests
```

## Security

- GitHub tokens encrypted at rest (Fernet); signed, HttpOnly, SameSite session cookies
- OAuth `state` (single use, constant-time compare); Origin checks against CSRF
- Per-user and per-IP rate limits, request size caps, strict input validation
- Every query scoped to its owner; security headers (CSP, frame denial, nosniff)
- Dependencies pinned and audited (`pip-audit`, `npm audit`); container runs as non-root

Accepted risk: commit contents and READMEs reach the model, so a malicious repo could steer the
ghost's wording (prompt injection). Output is always rendered as escaped text and only shown to
the repo's owner.

Found a vulnerability? Please report it privately; see [SECURITY.md](SECURITY.md).

## License

[GNU AGPL-3.0](LICENSE). You may use, modify and share GhostCommit, but if you run a modified
version as a service, you must publish your source under the same license.
