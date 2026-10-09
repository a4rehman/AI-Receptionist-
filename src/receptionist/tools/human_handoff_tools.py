import uuid

from pydantic import BaseModel, Field

from receptionist.db.models import HandoffPriority, HandoffStatus, HumanHandoff
from receptionist.tools.registry import ToolContext, ToolResult, tool


class CreateHandoffArgs(BaseModel):
    reason: str = Field(..., description="Reason for human handoff")
    priority: str = Field("medium", description="Priority level: low, medium, high, urgent")
    customer_id: str | None = Field(None, description="Customer ID if known")


@tool(name="create_handoff", description="Create a human handoff request", input_schema=CreateHandoffArgs, permission="write")
async def create_handoff(args: CreateHandoffArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        try:
            priority = HandoffPriority(args.priority)
        except ValueError:
            priority = HandoffPriority.MEDIUM

        handoff = HumanHandoff(
            id=f"ho_{uuid.uuid4().hex[:12]}",
            tenant_id=ctx.tenant_id,
            conversation_id=ctx.conversation_id,
            customer_id=args.customer_id or ctx.customer_id,
            reason=args.reason,
            priority=priority,
            status=HandoffStatus.OPEN,
        )
        session.add(handoff)
        await session.commit()
        return ToolResult(success=True, data={
            "handoff_id": handoff.id,
            "status": handoff.status.value,
            "priority": handoff.priority.value,
        })
