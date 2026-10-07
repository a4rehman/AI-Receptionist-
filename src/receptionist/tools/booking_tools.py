import uuid
from datetime import datetime, timedelta, time
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import Appointment, AppointmentStatus, AppointmentStatusHistory, Service, Staff, Customer
from receptionist.services.availability import AvailabilityService
from receptionist.utils.idempotency import generate_idempotency_key, check_idempotency, save_idempotency_result


class CreateBookingArgs(BaseModel):
    customer_id: str = Field(..., description="Customer ID")
    service_id: str = Field(..., description="Service ID")
    staff_id: Optional[str] = Field(None, description="Preferred staff ID")
    date: str = Field(..., description="Appointment date (YYYY-MM-DD)")
    time: str = Field(..., description="Appointment time (HH:MM)")
    timezone: str = Field("UTC", description="Timezone")
    notes: Optional[str] = Field(None, description="Optional notes")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for safe retries")


@tool(name="create_booking", description="Create a new appointment booking", input_schema=CreateBookingArgs, permission="write")
async def create_booking(args: CreateBookingArgs, ctx: ToolContext) -> ToolResult:
    if ctx.db_session is not None:
        return await _create_booking_with_session(args, ctx, ctx.db_session)
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        return await _create_booking_with_session(args, ctx, session)


async def _create_booking_with_session(args: CreateBookingArgs, ctx: ToolContext, session) -> ToolResult:
    idem_key = args.idempotency_key or generate_idempotency_key()

    existing = await check_idempotency(session, ctx.tenant_id, "create_booking", idem_key)
    if existing:
        return ToolResult(success=True, data=existing)

    service_result = await session.execute(
        select(Service).where(Service.id == args.service_id, Service.tenant_id == ctx.tenant_id)
    )
    service = service_result.scalar_one_or_none()
    if not service:
        return ToolResult(success=False, error="Service not found")

    customer_result = await session.execute(
        select(Customer).where(Customer.id == args.customer_id, Customer.tenant_id == ctx.tenant_id)
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        return ToolResult(success=False, error="Customer not found")

    try:
        from datetime import date as date_type
        target_date = date_type.fromisoformat(args.date)
        hour, minute = map(int, args.time.split(":"))
    except (ValueError, AttributeError):
        return ToolResult(success=False, error="Invalid date or time format")

    availability = AvailabilityService(session)
    slots = await availability.get_available_slots(
        tenant_id=ctx.tenant_id,
        service_id=args.service_id,
        target_date=target_date,
        staff_id=args.staff_id,
        timezone=args.timezone,
    )

    selected_slot = None
    for slot in slots:
        if slot["start_time"] == args.time:
            selected_slot = slot
            break

    if not selected_slot:
        return ToolResult(success=False, error="Selected time slot is not available")

    start_dt = datetime.combine(target_date, time(hour, minute))
    end_dt = start_dt + timedelta(minutes=service.duration_minutes)

    appointment = Appointment(
        id=f"apt_{uuid.uuid4().hex[:12]}",
        tenant_id=ctx.tenant_id,
        customer_id=args.customer_id,
        staff_id=selected_slot["staff_id"],
        service_id=args.service_id,
        start_time=start_dt,
        end_time=end_dt,
        status=AppointmentStatus.CONFIRMED,
        idempotency_key=idem_key,
        notes=args.notes,
    )
    session.add(appointment)

    status_history = AppointmentStatusHistory(
        appointment_id=appointment.id,
        to_status=AppointmentStatus.CONFIRMED.value,
        changed_by="agent",
    )
    session.add(status_history)

    await session.commit()

    result_data = {
        "appointment_id": appointment.id,
        "date": args.date,
        "time": args.time,
        "service": service.name,
        "staff": selected_slot.get("staff_name"),
        "status": "confirmed",
    }
    await save_idempotency_result(session, ctx.tenant_id, "create_booking", idem_key, result_data)
    await session.commit()

    return ToolResult(success=True, data=result_data)
