import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import get_session, init_db
from app.middleware import SecurityMiddleware
from app.routers import auth, ghost, hauntings, internal, repos
from app.services.backboard import BackboardError
from app.services.github import GitHubError

settings = get_settings()
log = logging.getLogger(__name__)
PRODUCTION = settings.app_url.startswith("https://")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# Interactive API docs only in development: no need to hand attackers a map in production.
app = FastAPI(
    title="GhostCommit",
    lifespan=lifespan,
    docs_url=None if PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if PRODUCTION else "/openapi.json",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=7 * 24 * 3600,
    same_site="lax",
    https_only=PRODUCTION,
)
app.add_middleware(SecurityMiddleware)


@app.exception_handler(GitHubError)
async def github_error(request: Request, exc: GitHubError) -> JSONResponse:
    # A revoked/regenerated token is not a server bug: tell the UI to send the user through login again.
    if exc.status_code == 401:
        return JSONResponse({"detail": "github_reconnect"}, status_code=401)
    # Details stay in our logs; clients get a generic message (no upstream internals leaked).
    log.warning("GitHub error: %s", exc)
    return JSONResponse({"detail": "GitHub request failed. Try again soon."}, status_code=502)


@app.exception_handler(BackboardError)
async def backboard_error(request: Request, exc: BackboardError) -> JSONResponse:
    log.warning("Backboard error: %s", exc)
    return JSONResponse({"detail": "The ghost is unreachable right now. Try again soon."}, status_code=502)


app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(ghost.router)
app.include_router(hauntings.router)
app.include_router(internal.router)


@app.get("/api/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}


def resolve_static(static_dir: Path, path: str) -> Path:
    """Map a URL path to a file inside static_dir, falling back to index.html (SPA routing).

    Resolving and checking containment blocks path traversal like /..%2F..%2Fapp/config.py.
    """
    root = static_dir.resolve()
    candidate = (root / path).resolve()
    if candidate.is_file() and candidate.is_relative_to(root):
        return candidate
    return root / "index.html"


# In production the built React app is copied to ./static and served from here,
# so the frontend and API share one origin (no CORS, cookies just work).
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        return FileResponse(resolve_static(STATIC_DIR, path))
