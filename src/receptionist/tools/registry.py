import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

ToolFunction = Callable[..., Awaitable[Any]]

WRITE_PERMISSIONS = {"write"}
READ_PERMISSIONS = {"read"}


class ToolContext:
    def __init__(self, tenant_id: str, conversation_id: str, customer_id: str | None = None, db_session: Any = None, enabled_tools: list[str] | None = None, run_id: str | None = None):
        self.tenant_id = tenant_id
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self.db_session = db_session
        self.enabled_tools = enabled_tools or []
        self.run_id = run_id

    async def get_session(self):
        if self.db_session is not None:
            return self.db_session
        from receptionist.db.engine import async_session_factory
        return async_session_factory()

    def is_tool_enabled(self, tool_name: str) -> bool:
        return not self.enabled_tools or tool_name in self.enabled_tools


class ToolResult:
    def __init__(self, success: bool, data: Any = None, error: str | None = None):
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
                    await _log_agent_event(ctx, name, "completed", duration_ms)
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
                    await _log_agent_event(ctx, name, "failed", duration_ms)
                raise

        _tool_registry[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            permission=permission,
            func=wrapper,
        )
        return wrapper
    return decorator


def get_tool(name: str) -> ToolDefinition | None:
    return _tool_registry.get(name)


def list_tools() -> list[ToolDefinition]:
    return list(_tool_registry.values())


def get_tools_for_tenant(enabled_tools: list[str]) -> list[ToolDefinition]:
    return [t for t in _tool_registry.values() if t.name in enabled_tools]


async def _log_tool_call(ctx: ToolContext, tool_name: str, args: tuple, result: Any, duration_ms: int, error: str | None) -> None:
    if not getattr(ctx, "run_id", None):
        return
    try:
        from pydantic import BaseModel

        from receptionist.db.models import ToolCall

        raw_args = args[0] if args else None
        if isinstance(raw_args, BaseModel):
            arguments = raw_args.model_dump()
        elif raw_args is not None:
            arguments = {"input": str(raw_args)}
        else:
            arguments = None

        tool_call = ToolCall(
            run_id=ctx.run_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result.to_dict() if hasattr(result, "to_dict") else ({"output": str(result)} if result else None),
            status="failed" if error else "completed",
            duration_ms=duration_ms,
            error=error,
        )
        ctx.db_session.add(tool_call)
        await ctx.db_session.flush()
    except Exception:  # noqa: BLE001 - audit logging must never break the tool call
        logger.warning("failed to log tool call", tool_name=tool_name)


async def _log_agent_event(ctx: ToolContext, tool_name: str, status: str, duration_ms: int) -> None:
    if not getattr(ctx, "run_id", None):
        return
    try:
        from receptionist.db.models import AgentEvent

        ctx.db_session.add(AgentEvent(
            run_id=ctx.run_id,
            event_type="tool_executed",
            node_name="tool_execution",
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
        ))
        await ctx.db_session.flush()
    except Exception:  # noqa: BLE001 - audit logging must never break the tool call
        logger.warning("failed to log agent event", tool_name=tool_name)
