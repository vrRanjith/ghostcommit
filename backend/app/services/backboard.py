"""Thin async client for the Backboard REST API.

Mapping: one tracked repo = one Backboard assistant. Memory is scoped per assistant,
so everything the ghost learns about a repo is shared across all of its threads.
"""

import asyncio
from typing import Any

import httpx

from app.config import get_settings

MAX_ATTEMPTS = 3


class BackboardError(RuntimeError):
    pass


class BackboardClient:
    def __init__(self) -> None:
        s = get_settings()
        self._llm_provider = s.llm_provider
        self._model_name = s.model_name
        self._http = httpx.AsyncClient(
            base_url=s.backboard_base_url,
            headers={"X-API-Key": s.backboard_api_key},
            timeout=httpx.Timeout(60.0),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        # Retry transient failures (5xx, network) with backoff; 4xx means our request is wrong.
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = await self._http.request(method, path, **kwargs)
            except httpx.TransportError as e:
                if attempt == MAX_ATTEMPTS - 1:
                    raise BackboardError(f"{method} {path} -> {e!r}") from e
            else:
                if resp.status_code < 500 or attempt == MAX_ATTEMPTS - 1:
                    break
            await asyncio.sleep(2**attempt)
        if resp.is_error:
            raise BackboardError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    async def create_assistant(self, name: str, system_prompt: str) -> str:
        data = await self._request("POST", "/assistants", json={"name": name, "system_prompt": system_prompt})
        return data["assistant_id"]

    async def delete_assistant(self, assistant_id: str) -> None:
        await self._request("DELETE", f"/assistants/{assistant_id}")

    async def create_thread(self, assistant_id: str) -> str:
        data = await self._request("POST", f"/assistants/{assistant_id}/threads", json={})
        return data["thread_id"]

    async def add_memory(self, assistant_id: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if metadata:
            body["metadata"] = metadata
        return await self._request("POST", f"/assistants/{assistant_id}/memories", json=body)

    async def list_memories(self, assistant_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/assistants/{assistant_id}/memories")

    async def delete_memory(self, assistant_id: str, memory_id: str) -> None:
        await self._request("DELETE", f"/assistants/{assistant_id}/memories/{memory_id}")

    async def search_memories(self, assistant_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        return await self._request(
            "POST", f"/assistants/{assistant_id}/memories/search", json={"query": query, "limit": limit}
        )

    async def send_message(self, thread_id: str, content: str, memory: str = "Auto") -> str:
        # This endpoint takes form data, not JSON.
        data = await self._request(
            "POST",
            f"/threads/{thread_id}/messages",
            data={
                "content": content,
                "stream": "false",
                "memory": memory,
                "llm_provider": self._llm_provider,
                "model_name": self._model_name,
            },
        )
        content = data["content"]
        # Backboard reports model failures as a 200 with the error in the reply text.
        if content.startswith("LLM Error:"):
            raise BackboardError(content[:500])
        return content


async def _smoke_test() -> None:
    """Run with: docker compose run --rm api python -m app.services.backboard"""
    bb = BackboardClient()
    try:
        assistant_id = await bb.create_assistant(
            "ghostcommit-smoke-test", "You are a terse assistant. Answer in one sentence."
        )
        print("assistant:", assistant_id)
        await bb.add_memory(assistant_id, "The project's last blocker was the OAuth redirect URL.")
        thread_id = await bb.create_thread(assistant_id)
        print("thread:", thread_id)
        reply = await bb.send_message(thread_id, "What was the project's last blocker?")
        print("reply:", reply)
    finally:
        await bb.aclose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_smoke_test())
