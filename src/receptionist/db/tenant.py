from contextvars import ContextVar
from typing import Optional

tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_context", default=None)


def get_current_tenant() -> Optional[str]:
    return tenant_context.get()


def set_current_tenant(tenant_id: str) -> None:
    tenant_context.set(tenant_id)


def clear_current_tenant() -> None:
    tenant_context.set(None)
