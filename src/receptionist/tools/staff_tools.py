
from pydantic import BaseModel, Field
from sqlalchemy import select

from receptionist.db.models import Service, Staff, StaffSchedule, StaffService
from receptionist.tools.registry import ToolContext, ToolResult, tool


class ListStaffArgs(BaseModel):
    department: str | None = Field(None, description="Filter by department")
    specialization: str | None = Field(None, description="Filter by specialization")
    is_active: bool = Field(True, description="Only return active staff")


class GetStaffArgs(BaseModel):
    staff_id: str = Field(..., description="Staff ID to look up")


class SearchStaffArgs(BaseModel):
    query: str = Field(..., description="Search query (name, specialization, department)")


class GetStaffServicesArgs(BaseModel):
    staff_id: str = Field(..., description="Staff ID")


class GetStaffScheduleArgs(BaseModel):
    staff_id: str = Field(..., description="Staff ID")


@tool(name="list_staff", description="List all staff members, optionally filtered", input_schema=ListStaffArgs, permission="read")
async def list_staff(args: ListStaffArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        query = select(Staff).where(Staff.tenant_id == ctx.tenant_id, Staff.is_active == args.is_active)
        if args.department:
            query = query.where(Staff.department == args.department)
        if args.specialization:
            query = query.where(Staff.specialization.ilike(f"%{args.specialization}%"))
        result = await session.execute(query)
        staff_list = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "role": s.role,
                "specialization": s.specialization,
                "department": s.department,
                "email": s.email,
                "phone": s.phone,
            }
            for s in staff_list
        ])


@tool(name="get_staff", description="Get staff member details by ID", input_schema=GetStaffArgs, permission="read")
async def get_staff(args: GetStaffArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Staff).where(Staff.id == args.staff_id, Staff.tenant_id == ctx.tenant_id)
        )
        staff = result.scalar_one_or_none()
        if not staff:
            return ToolResult(success=False, error="Staff not found")
        return ToolResult(success=True, data={
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "specialization": staff.specialization,
            "department": staff.department,
            "email": staff.email,
            "phone": staff.phone,
        })


@tool(name="search_staff", description="Search staff by name, specialization, or department", input_schema=SearchStaffArgs, permission="read")
async def search_staff(args: SearchStaffArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        query = select(Staff).where(
            Staff.tenant_id == ctx.tenant_id,
            Staff.is_active == True,
        )
        if args.query:
            query = query.where(
                (Staff.name.ilike(f"%{args.query}%")) |
                (Staff.specialization.ilike(f"%{args.query}%")) |
                (Staff.department.ilike(f"%{args.query}%"))
            )
        result = await session.execute(query)
        staff_list = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "role": s.role,
                "specialization": s.specialization,
                "department": s.department,
            }
            for s in staff_list
        ])


@tool(name="get_staff_services", description="Get services offered by a staff member", input_schema=GetStaffServicesArgs, permission="read")
async def get_staff_services(args: GetStaffServicesArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service)
            .join(StaffService, Service.id == StaffService.service_id)
            .where(StaffService.staff_id == args.staff_id, Service.tenant_id == ctx.tenant_id)
        )
        services = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "duration_minutes": s.duration_minutes,
                "price": s.price,
            }
            for s in services
        ])


@tool(name="get_staff_schedule", description="Get weekly schedule for a staff member", input_schema=GetStaffScheduleArgs, permission="read")
async def get_staff_schedule(args: GetStaffScheduleArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(StaffSchedule).where(
                StaffSchedule.staff_id == args.staff_id,
                StaffSchedule.is_active == True,
            ).order_by(StaffSchedule.day_of_week)
        )
        schedules = result.scalars().all()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return ToolResult(success=True, data=[
            {
                "day": days[s.day_of_week],
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in schedules
        ])
