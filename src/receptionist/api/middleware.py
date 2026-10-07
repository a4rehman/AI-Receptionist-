from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from receptionist.config import get_settings

_settings = get_settings()


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)

        api_key = request.headers.get(_settings.api_key_header)
        if not api_key and not _settings.is_development:
            raise HTTPException(status_code=401, detail="API key required")

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response
