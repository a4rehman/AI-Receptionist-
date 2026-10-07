import uuid
from datetime import datetime, timedelta, time
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import Appointment, AppointmentStatus, AppointmentStatusHistory, Service
from receptionist.services.availability import AvailabilityService
from receptionist.utils.idempotency import generate_idempotency_key, check_idempotency, save_idempotency_result


class RescheduleBookingArgs(BaseModel):
    appointment_id: str = Field(..., description="Appointment ID to reschedule")
    customer_id: str = Field(..., description="Customer ID (for verification)")
    new_date: str = Field(..., description="New date (YYYY-MM-DD)")
    new_time: str = Field(..., description="New time (HH:MM)")
    timezone: str = Field("UTC", description="Timezone")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


@tool(name="reschedule_booking", description="Reschedule an existing appointment to a new date/time", input_schema=RescheduleBookingArgs, permission="write")
async def reschedule_booking(args: RescheduleBookingArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        idem_key = args.idempotency_key or generate_idempotency_key()

        existing = await check_idempotency(session, ctx.tenant_id, "reschedule_booking", idem_key)
        if existing:
            return ToolResult(success=True, data=existing)

        result = await session.execute(
            select(Appointment).where(
                Appointment.id == args.appointment_id,
                Appointment.tenant_id == ctx.tenant_id,
                Appointment.customer_id == args.customer_id,
            )
        )
        appointment = result.scalar_one_or_none()
        if not appointment:
            return ToolResult(success=False, error="Appointment not found or does not belong to this customer")

        if appointment.status == AppointmentStatus.CANCELLED:
            return ToolResult(success=False, error="Cannot reschedule a cancelled appointment")

        service_result = await session.execute(
            select(Service).where(Service.id == appointment.service_id)
        )
        service = service_result.scalar_one_or_none()
        duration = service.duration_minutes if service else 30

        try:
            from datetime import date as date_type
            target_date = date_type.fromisoformat(args.new_date)
            hour, minute = map(int, args.new_time.split(":"))
        except (ValueError, AttributeError):
            return ToolResult(success=False, error="Invalid date or time format")

        availability = AvailabilityService(session)
        slots = await availability.get_available_slots(
            tenant_id=ctx.tenant_id,
            service_id=appointment.service_id,
            target_date=target_date,
            staff_id=appointment.staff_id,
            timezone=args.timezone,
        )

        selected_slot = None
        for slot in slots:
            if slot["start_time"] == args.new_time:
                selected_slot = slot
                break

        if not selected_slot:
            return ToolResult(success=False, error="Selected time slot is not available")

        old_start = appointment.start_time
        old_end = appointment.end_time

        new_start = datetime.combine(target_date, time(hour, minute))
        new_end = new_start + timedelta(minutes=duration)

        appointment.start_time = new_start
        appointment.end_time = new_end
        if selected_slot["staff_id"]:
            appointment.staff_id = selected_slot["staff_id"]

        status_history = AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=appointment.status.value if appointment.status else None,
            to_status=appointment.status.value if appointment.status else None,
            changed_by="agent",
        )
        session.add(status_history)

        await session.commit()

        result_data = {
            "appointment_id": appointment.id,
            "old_date": old_start.isoformat(),
            "old_time": old_start.strftime("%H:%M"),
            "new_date": args.new_date,
            "new_time": args.new_time,
            "status": "rescheduled",
        }
        await save_idempotency_result(session, ctx.tenant_id, "reschedule_booking", idem_key, result_data)
        await session.commit()

        return ToolResult(success=True, data=result_data)
