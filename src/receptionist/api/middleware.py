from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from receptionist.api.auth import resolve_api_key
from receptionist.config import get_settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
}


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=401, headers=SECURITY_HEADERS)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate the tenant API key on every /api/v1 request and bind its tenant."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1"):
            api_key = request.headers.get(get_settings().api_key_header)
            if not api_key:
                return _unauthorized("API key required")
            tenant_id = resolve_api_key(api_key)
            if tenant_id is None:
                return _unauthorized("Invalid API key")
            request.state.tenant_id = tenant_id

        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
