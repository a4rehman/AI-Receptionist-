from typing import Any, Callable, Awaitable, Optional
from pydantic import BaseModel
from functools import wraps
import time
import structlog

logger = structlog.get_logger()

ToolFunction = Callable[..., Awaitable[Any]]


class ToolContext:
    def __init__(self, tenant_id: str, conversation_id: str, customer_id: Optional[str] = None, db_session: Any = None):
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self.db_session = db_session

    async def get_session(self):
        if self.db_session is not None:
            return self.db_session
        from receptionist.db.engine import async_session_factory
        return async_session_factory()


class ToolResult:
    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: type[BaseModel],
        permission: str,
        func: ToolFunction,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.permission = permission
        self.func = func


_tool_registry: dict[str, ToolDefinition] = {}


def tool(name: str, description: str, input_schema: type[BaseModel], permission: str = "read"):
    def decorator(func: ToolFunction) -> ToolFunction:
        _tool_registry[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            permission=permission,
            func=func,
        )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                logger.info(
                    "tool_executed",
                    tool_name=name,
                    duration_ms=duration_ms,
                    success=True,
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(
                    "tool_failed",
                    tool_name=name,
                    duration_ms=duration_ms,
                    error=str(e),
                )
                raise

        return wrapper
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    return _tool_registry.get(name)


def list_tools() -> list[ToolDefinition]:
    return list(_tool_registry.values())


def get_tools_for_tenant(enabled_tools: list[str]) -> list[ToolDefinition]:
    return [t for t in _tool_registry.values() if t.name in enabled_tools]
