"""HTTP-level protections applied to every request: CSRF origin check, body size cap,
and security headers."""

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY_BYTES = 64 * 1024  # our largest legit body is a 2,000-char chat message

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        # React sets inline style attributes; fonts come from Google Fonts.
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https://avatars.githubusercontent.com",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self.allowed_origin = _origin(settings.app_url)
        self.https = settings.app_url.startswith("https://")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in UNSAFE_METHODS:
            # CSRF defense in depth (on top of SameSite=Lax cookies): browsers always send
            # Origin on cross-site POSTs, so reject any that didn't come from our own pages.
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")
            if (origin and origin != self.allowed_origin) or (
                not origin and fetch_site not in (None, "same-origin", "none")
            ):
                return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)

            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)

        response = await call_next(request)

        h = response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        h["Content-Security-Policy"] = CSP
        if self.https:
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(("/api", "/auth")):
            h["Cache-Control"] = "no-store"  # personal data must never sit in shared caches
        return response
