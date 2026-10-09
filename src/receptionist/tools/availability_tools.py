from datetime import date

from pydantic import BaseModel, Field

from receptionist.services.availability import AvailabilityService
from receptionist.tools.registry import ToolContext, ToolResult, tool


class GetAvailabilityArgs(BaseModel):
    service_id: str = Field(..., description="Service ID to check availability for")
    date: str = Field(..., description="Date to check (YYYY-MM-DD)")
    staff_id: str | None = Field(None, description="Optional staff ID to filter by")
    timezone: str = Field("UTC", description="Timezone for the business")


@tool(name="get_availability", description="Get available time slots for a service on a specific date", input_schema=GetAvailabilityArgs, permission="read")
async def get_availability(args: GetAvailabilityArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        service = AvailabilityService(session)
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            return ToolResult(success=False, error="Invalid date format. Use YYYY-MM-DD")

        slots = await service.get_available_slots(
            tenant_id=ctx.tenant_id,
            service_id=args.service_id,
            target_date=target_date,
            staff_id=args.staff_id,
            timezone=args.timezone,
        )
        return ToolResult(success=True, data=slots)
