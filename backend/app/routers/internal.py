"""Machine-to-machine endpoints, called by the scheduler (GitHub Actions), never by browsers."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from app import haunter
from app.config import get_settings
from app.ratelimit import haunt_limit

router = APIRouter(prefix="/internal")


@router.post("/haunt", dependencies=[Depends(haunt_limit)])
async def haunt(authorization: str = Header(default="")) -> dict[str, int]:
    """Run the daily haunter. Requires `Authorization: Bearer <HAUNT_SECRET>`."""
    secret = get_settings().haunt_secret
    if not secret:
        # Disabled unless configured: answer as if the endpoint didn't exist.
        raise HTTPException(status_code=404, detail="Not Found")
    # Constant-time comparison so response timing can't leak the secret character by character.
    if not secrets.compare_digest(authorization.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await haunter.run(force=False)
