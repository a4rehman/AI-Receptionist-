import hashlib
import time
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from receptionist.api.middleware import SECURITY_HEADERS
from receptionist.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limit for /api/v1, keyed per API key (or client IP).

    The limit is enforced by returning a 429 response rather than raising, so
    an exhausted budget never surfaces as an unhandled exception. Requests
    without an API key fall back to per-IP accounting.
    """

    def __init__(
        self,
        app,
        max_requests: int | None = None,
        window_seconds: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self.requests: dict[str, list[float]] = {}

    def _limit(self) -> int:
        return self.max_requests if self.max_requests is not None else get_settings().api_rate_limit

    def _window(self) -> int:
        return self.window_seconds if self.window_seconds is not None else get_settings().api_rate_limit_window

    @staticmethod
    def _identity(request: Request) -> str:
        settings = get_settings()
        api_key = request.headers.get(settings.api_key_header)
        if api_key:
            digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:24]
            return f"key:{digest}"
        host = request.client.host if request.client else "unknown"
        return f"ip:{host}"

    def _prune(self, window: int) -> None:
        """Drop idle buckets so the tracker cannot grow without bound."""
        if len(self.requests) <= 2048:
            return
        cutoff = self.clock() - window
        for identity in [k for k, stamps in self.requests.items() if not stamps or stamps[-1] < cutoff]:
            del self.requests[identity]

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        max_requests = self._limit()
        window = self._window()
        if max_requests <= 0:
            return await call_next(request)

        now = self.clock()
        identity = self._identity(request)
        stamps = [ts for ts in self.requests.get(identity, []) if now - ts < window]

        if len(stamps) >= max_requests:
            oldest = stamps[0]
            retry_after = max(1, int(window - (now - oldest)) + 1)
            self.requests[identity] = stamps
            self._prune(window)
            return JSONResponse(
                {"detail": "Rate limit exceeded", "retry_after_seconds": retry_after},
                status_code=429,
                headers={"Retry-After": str(retry_after), **SECURITY_HEADERS},
            )

        stamps.append(now)
        self.requests[identity] = stamps
        self._prune(window)

        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
