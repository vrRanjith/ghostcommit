"""Minimal async GitHub REST client, authenticated as the logged-in user."""

from typing import Any

import httpx

API = "https://api.github.com"


class GitHubError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def exchange_code_for_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> str:
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri},
        )
    data = resp.json()
    # GitHub returns 200 even for a bad/expired code; the error is in the body.
    if "access_token" not in data:
        raise GitHubError(f"token exchange failed: {data.get('error_description') or data}")
    return data["access_token"]


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        resp = await self._http.get(path, params=params or None)
        if resp.is_error:
            raise GitHubError(f"GET {path} -> {resp.status_code}: {resp.text[:300]}", resp.status_code)
        return resp.json()

    async def get_user(self) -> dict[str, Any]:
        return await self._get("/user")

    async def get_primary_email(self) -> str | None:
        emails = await self._get("/user/emails")
        primary = next((e for e in emails if e["primary"] and e["verified"]), None)
        return primary["email"] if primary else None

    async def list_repos(self) -> list[dict[str, Any]]:
        # Most recently pushed first, so the repos you actually work on are on top.
        return await self._get("/user/repos", sort="pushed", per_page=100, affiliation="owner")

    async def get_repo(self, full_name: str) -> dict[str, Any]:
        return await self._get(f"/repos/{full_name}")

    async def list_commits(self, full_name: str, per_page: int = 30) -> list[dict[str, Any]]:
        try:
            return await self._get(f"/repos/{full_name}/commits", per_page=per_page)
        except GitHubError as e:
            if e.status_code == 409:  # "Git Repository is empty": nothing to remember, not an error
                return []
            raise

    async def get_commit(self, full_name: str, sha: str) -> dict[str, Any]:
        """Single commit including changed files and their patches (diffs)."""
        return await self._get(f"/repos/{full_name}/commits/{sha}")

    async def get_readme(self, full_name: str) -> str | None:
        resp = await self._http.get(f"/repos/{full_name}/readme", headers={"Accept": "application/vnd.github.raw+json"})
        return resp.text if resp.status_code == 200 else None
