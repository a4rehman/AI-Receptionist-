from typing import Any, Callable, Awaitable, Optional
from pydantic import BaseModel
from functools import wraps
import time
import structlog

logger = structlog.get_logger()

ToolFunction = Callable[..., Awaitable[Any]]

WRITE_PERMISSIONS = {"write"}
READ_PERMISSIONS = {"read"}


class ToolContext:
    def __init__(self, tenant_id: str, conversation_id: str, customer_id: Optional[str] = None, db_session: Any = None, enabled_tools: Optional[list[str]] = None):
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self.db_session = db_session
        self.enabled_tools = enabled_tools or []

    async def get_session(self):
        if self.db_session is not None:
            return self.db_session
        from receptionist.db.engine import async_session_factory
        return async_session_factory()

    def is_tool_enabled(self, tool_name: str) -> bool:
        return not self.enabled_tools or tool_name in self.enabled_tools


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
            ctx = kwargs.get("ctx") or (args[1] if len(args) > 1 else None)

            if ctx and hasattr(ctx, "is_tool_enabled") and not ctx.is_tool_enabled(name):
                return ToolResult(success=False, error=f"Tool '{name}' is not enabled for this tenant")

            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                logger.info(
                    "tool_executed",
                    tool_name=name,
                    duration_ms=duration_ms,
                    success=True,
                )
                if ctx and hasattr(ctx, "db_session") and ctx.db_session:
                    await _log_tool_call(ctx, name, args, result, duration_ms, None)
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(
                    "tool_failed",
                    tool_name=name,
                    duration_ms=duration_ms,
                    error=str(e),
                )
                if ctx and hasattr(ctx, "db_session") and ctx.db_session:
                    await _log_tool_call(ctx, name, args, None, duration_ms, str(e))
                raise

        return wrapper
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    return _tool_registry.get(name)


def list_tools() -> list[ToolDefinition]:
    return list(_tool_registry.values())


def get_tools_for_tenant(enabled_tools: list[str]) -> list[ToolDefinition]:
    return [t for t in _tool_registry.values() if t.name in enabled_tools]


async def _log_tool_call(ctx: ToolContext, tool_name: str, args: tuple, result: Any, duration_ms: int, error: Optional[str]) -> None:
    try:
        from receptionist.db.models import ToolCall
        tool_call = ToolCall(
            run_id=ctx.conversation_id,
            tool_name=tool_name,
            arguments=str(args[0]) if args else None,
            result=result.to_dict() if hasattr(result, "to_dict") else str(result) if result else None,
            status="failed" if error else "completed",
            duration_ms=duration_ms,
            error=error,
        )
        ctx.db_session.add(tool_call)
        await ctx.db_session.flush()
    except Exception:
        logger.warning("failed to log tool call", tool_name=tool_name)
