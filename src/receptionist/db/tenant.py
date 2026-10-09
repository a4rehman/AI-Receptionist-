from contextvars import ContextVar

tenant_context: ContextVar[str | None] = ContextVar("tenant_context", default=None)


def get_current_tenant() -> str | None:
    return tenant_context.get()


def set_current_tenant(tenant_id: str) -> None:
    tenant_context.set(tenant_id)


def clear_current_tenant() -> None:
    tenant_context.set(None)
