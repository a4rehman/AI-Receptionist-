import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from receptionist.config import get_settings

security = HTTPBearer(auto_error=False)


def resolve_api_key(api_key: str | None) -> str | None:
    """Return the tenant_id bound to a valid API key, or None. Timing-safe."""
    if not api_key:
        return None
    given = hashlib.sha256(api_key.encode("utf-8")).digest()
    matched_tenant: str | None = None
    for tenant_id, secret in get_settings().parsed_api_keys:
        expected = hashlib.sha256(secret.encode("utf-8")).digest()
        if hmac.compare_digest(given, expected) and matched_tenant is None:
            matched_tenant = tenant_id
    return matched_tenant


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, get_settings().secret_key, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    request: Request = None,  # FastAPI only injects bare Request annotations
) -> dict:
    settings = get_settings()
    if settings.is_development and not credentials:
        return {"sub": "dev_user", "role": "admin", "tenant_id": "*"}

    if not credentials:
        api_key = request.headers.get(settings.api_key_header) if request else None
        tenant_id = resolve_api_key(api_key)
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"sub": f"api_{api_key[:8]}", "role": "api", "tenant_id": tenant_id}

    payload = verify_token(credentials.credentials)
    return payload


def require_role(allowed_roles: list[str]):
    async def role_checker(user: dict = Depends(get_current_user)) -> dict:  # noqa: B008
        if user.get("role") not in allowed_roles and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker
