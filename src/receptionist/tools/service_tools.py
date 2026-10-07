from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import Service, StaffService, Staff


class ListServicesArgs(BaseModel):
    is_active: bool = Field(True, description="Only return active services")


class GetServiceArgs(BaseModel):
    service_id: str = Field(..., description="Service ID to look up")


class SearchServicesArgs(BaseModel):
    query: str = Field(..., description="Search query for service name or description")


class GetServicePriceArgs(BaseModel):
    service_id: str = Field(..., description="Service ID")


class GetServiceDurationArgs(BaseModel):
    service_id: str = Field(..., description="Service ID")


class GetServiceStaffArgs(BaseModel):
    service_id: str = Field(..., description="Service ID")


@tool(name="list_services", description="List all services offered by the business", input_schema=ListServicesArgs, permission="read")
async def list_services(args: ListServicesArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(Service.tenant_id == ctx.tenant_id, Service.is_active == args.is_active)
        )
        services = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "duration_minutes": s.duration_minutes,
                "price": s.price,
                "currency": s.currency,
            }
            for s in services
        ])


@tool(name="get_service", description="Get service details by ID", input_schema=GetServiceArgs, permission="read")
async def get_service(args: GetServiceArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(Service.id == args.service_id, Service.tenant_id == ctx.tenant_id)
        )
        service = result.scalar_one_or_none()
        if not service:
            return ToolResult(success=False, error="Service not found")
        return ToolResult(success=True, data={
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "duration_minutes": service.duration_minutes,
            "price": service.price,
            "currency": service.currency,
        })


@tool(name="search_services", description="Search services by name or description", input_schema=SearchServicesArgs, permission="read")
async def search_services(args: SearchServicesArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(
                Service.tenant_id == ctx.tenant_id,
                Service.is_active == True,
                (Service.name.ilike(f"%{args.query}%")) | (Service.description.ilike(f"%{args.query}%")),
            )
        )
        services = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "duration_minutes": s.duration_minutes,
                "price": s.price,
            }
            for s in services
        ])


@tool(name="get_service_price", description="Get the price of a service", input_schema=GetServicePriceArgs, permission="read")
async def get_service_price(args: GetServicePriceArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(Service.id == args.service_id, Service.tenant_id == ctx.tenant_id)
        )
        service = result.scalar_one_or_none()
        if not service:
            return ToolResult(success=False, error="Service not found")
        return ToolResult(success=True, data={
            "service_id": service.id,
            "service_name": service.name,
            "price": service.price,
            "currency": service.currency,
        })


@tool(name="get_service_duration", description="Get the duration of a service", input_schema=GetServiceDurationArgs, permission="read")
async def get_service_duration(args: GetServiceDurationArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(Service.id == args.service_id, Service.tenant_id == ctx.tenant_id)
        )
        service = result.scalar_one_or_none()
        if not service:
            return ToolResult(success=False, error="Service not found")
        return ToolResult(success=True, data={
            "service_id": service.id,
            "service_name": service.name,
            "duration_minutes": service.duration_minutes,
        })


@tool(name="get_service_staff", description="Get staff members who can perform a service", input_schema=GetServiceStaffArgs, permission="read")
async def get_service_staff(args: GetServiceStaffArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Staff)
            .join(StaffService, Staff.id == StaffService.staff_id)
            .where(StaffService.service_id == args.service_id, Staff.tenant_id == ctx.tenant_id, Staff.is_active == True)
        )
        staff_list = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": s.id,
                "name": s.name,
                "role": s.role,
                "specialization": s.specialization,
            }
            for s in staff_list
        ])
