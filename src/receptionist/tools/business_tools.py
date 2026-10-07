from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import Tenant, BusinessHours, Location


class GetBusinessInfoArgs(BaseModel):
    pass


class GetBusinessHoursArgs(BaseModel):
    pass


class GetLocationsArgs(BaseModel):
    pass


@tool(name="get_business_info", description="Get general business information (name, type, contact, address)", input_schema=GetBusinessInfoArgs, permission="read")
async def get_business_info(args: GetBusinessInfoArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == ctx.tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return ToolResult(success=False, error="Tenant not found")
        return ToolResult(success=True, data={
            "business_name": tenant.business_name,
            "business_type": tenant.business_type.value if tenant.business_type else None,
            "phone": tenant.phone,
            "email": tenant.email,
            "website": tenant.website,
            "address": tenant.address,
            "timezone": tenant.timezone,
            "currency": tenant.currency,
        })


@tool(name="get_business_hours", description="Get business operating hours for each day of the week", input_schema=GetBusinessHoursArgs, permission="read")
async def get_business_hours(args: GetBusinessHoursArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(BusinessHours).where(BusinessHours.tenant_id == ctx.tenant_id).order_by(BusinessHours.day_of_week)
        )
        hours = result.scalars().all()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return ToolResult(success=True, data=[
            {
                "day": days[h.day_of_week],
                "start_time": h.start_time,
                "end_time": h.end_time,
                "is_closed": h.is_closed,
            }
            for h in hours
        ])


@tool(name="get_locations", description="Get business locations", input_schema=GetLocationsArgs, permission="read")
async def get_locations(args: GetLocationsArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Location).where(Location.tenant_id == ctx.tenant_id, Location.is_active == True)
        )
        locations = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": loc.id,
                "name": loc.name,
                "address": loc.address,
                "phone": loc.phone,
                "timezone": loc.timezone,
            }
            for loc in locations
        ])
