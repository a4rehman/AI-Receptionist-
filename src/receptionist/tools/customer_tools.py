
from pydantic import BaseModel, Field
from sqlalchemy import select

from receptionist.db.models import Appointment, Customer, Service, Staff
from receptionist.tools.registry import ToolContext, ToolResult, tool


class GetCustomerArgs(BaseModel):
    customer_id: str = Field(..., description="The customer ID to look up")


class FindCustomerByPhoneArgs(BaseModel):
    phone: str = Field(..., description="Phone number to search for")


class FindCustomerByEmailArgs(BaseModel):
    email: str = Field(..., description="Email address to search for")


class CreateCustomerArgs(BaseModel):
    first_name: str = Field(..., description="Customer first name")
    last_name: str = Field(..., description="Customer last name")
    email: str | None = Field(None, description="Customer email")
    phone: str | None = Field(None, description="Customer phone number")
    date_of_birth: str | None = Field(None, description="Date of birth (YYYY-MM-DD)")
    notes: str | None = Field(None, description="Additional notes")


class UpdateCustomerArgs(BaseModel):
    customer_id: str = Field(..., description="Customer ID to update")
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class GetCustomerAppointmentsArgs(BaseModel):
    customer_id: str = Field(..., description="Customer ID")
    status: str | None = Field(None, description="Filter by status")
    limit: int = Field(10, description="Maximum number of appointments")


@tool(name="get_customer", description="Get customer details by ID", input_schema=GetCustomerArgs, permission="read")
async def get_customer(args: GetCustomerArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.id == args.customer_id,
                Customer.tenant_id == ctx.tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return ToolResult(success=False, error="Customer not found")
        return ToolResult(success=True, data={
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone": customer.phone,
        })


@tool(name="find_customer_by_phone", description="Find a customer by phone number", input_schema=FindCustomerByPhoneArgs, permission="read")
async def find_customer_by_phone(args: FindCustomerByPhoneArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.phone == args.phone,
                Customer.tenant_id == ctx.tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return ToolResult(success=False, error="Customer not found")
        return ToolResult(success=True, data={
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone": customer.phone,
        })


@tool(name="find_customer_by_email", description="Find a customer by email address", input_schema=FindCustomerByEmailArgs, permission="read")
async def find_customer_by_email(args: FindCustomerByEmailArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.email == args.email,
                Customer.tenant_id == ctx.tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return ToolResult(success=False, error="Customer not found")
        return ToolResult(success=True, data={
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone": customer.phone,
        })


@tool(name="create_customer", description="Create a new customer record", input_schema=CreateCustomerArgs, permission="write")
async def create_customer(args: CreateCustomerArgs, ctx: ToolContext) -> ToolResult:
    import uuid

    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        customer = Customer(
            id=f"cust_{uuid.uuid4().hex[:12]}",
            tenant_id=ctx.tenant_id,
            first_name=args.first_name,
            last_name=args.last_name,
            email=args.email,
            phone=args.phone,
            notes=args.notes,
        )
        session.add(customer)
        await session.commit()
        return ToolResult(success=True, data={
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone": customer.phone,
        })


@tool(name="update_customer", description="Update customer information", input_schema=UpdateCustomerArgs, permission="write")
async def update_customer(args: UpdateCustomerArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.id == args.customer_id,
                Customer.tenant_id == ctx.tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return ToolResult(success=False, error="Customer not found")

        if args.first_name:
            customer.first_name = args.first_name
        if args.last_name:
            customer.last_name = args.last_name
        if args.email:
            customer.email = args.email
        if args.phone:
            customer.phone = args.phone
        if args.notes:
            customer.notes = args.notes

        await session.commit()
        return ToolResult(success=True, data={
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone": customer.phone,
        })


@tool(name="get_customer_appointments", description="Get appointments for a customer", input_schema=GetCustomerAppointmentsArgs, permission="read")
async def get_customer_appointments(args: GetCustomerAppointmentsArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        query = select(Appointment).where(
            Appointment.customer_id == args.customer_id,
            Appointment.tenant_id == ctx.tenant_id,
        )
        if args.status:
            query = query.where(Appointment.status == args.status)
        query = query.order_by(Appointment.start_time.desc()).limit(args.limit)

        result = await session.execute(query)
        appointments = result.scalars().all()

        data = []
        for apt in appointments:
            service_name = None
            staff_name = None
            if apt.service_id:
                svc_result = await session.execute(select(Service).where(Service.id == apt.service_id))
                svc = svc_result.scalar_one_or_none()
                if svc:
                    service_name = svc.name
            if apt.staff_id:
                staff_result = await session.execute(select(Staff).where(Staff.id == apt.staff_id))
                staff = staff_result.scalar_one_or_none()
                if staff:
                    staff_name = staff.name
            data.append({
                "id": apt.id,
                "service": service_name,
                "staff": staff_name,
                "start_time": apt.start_time.isoformat(),
                "end_time": apt.end_time.isoformat(),
                "status": apt.status.value if apt.status else None,
            })

        return ToolResult(success=True, data=data)
