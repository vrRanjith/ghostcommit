"""Sliding-window rate limits, so nobody can spam the endpoints that cost money (Backboard
memory writes, LLM calls) or hammer GitHub through us.

In-memory and per-process: fine for a single Render instance. Several instances would need
a shared store such as Redis.
"""

import math
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.deps import current_user
from app.models import User


class SlidingWindow:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[object, deque[float]] = defaultdict(deque)

    def hit(self, key: object) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = math.ceil(self.window - (now - hits[0]))
            raise HTTPException(
                status_code=429,
                detail="The spirits need rest. Try again in a moment.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


def per_user(limit: int, window_seconds: float):
    window = SlidingWindow(limit, window_seconds)

    async def dependency(user: User = Depends(current_user)) -> None:
        window.hit(user.id)

    dependency.window = window  # type: ignore[attr-defined]  (exposed for tests)
    return dependency


def per_ip(limit: int, window_seconds: float):
    window = SlidingWindow(limit, window_seconds)

    async def dependency(request: Request) -> None:
        # Behind Render's proxy, uvicorn --proxy-headers puts the real client IP here.
        window.hit(request.client.host if request.client else "unknown")

    dependency.window = window  # type: ignore[attr-defined]
    return dependency


# Budgets per endpoint group.
chat_limit = per_user(20, 60)
sync_limit = per_user(10, 60)
note_limit = per_user(10, 60)
summon_limit = per_user(20, 3600)
write_limit = per_user(30, 60)  # settings, banish, mark-read
github_list_limit = per_user(30, 60)
auth_limit = per_ip(20, 60)
haunt_limit = per_ip(5, 3600)  # the scheduler calls once a day; anything more is abuse

ALL_LIMITS = [chat_limit, sync_limit, note_limit, summon_limit, write_limit, github_list_limit, auth_limit, haunt_limit]
