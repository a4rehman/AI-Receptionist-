import uuid
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import Appointment, AppointmentStatus, AppointmentStatusHistory, Customer
from receptionist.utils.idempotency import generate_idempotency_key, check_idempotency, save_idempotency_result


class CancelBookingArgs(BaseModel):
    appointment_id: str = Field(..., description="Appointment ID to cancel")
    customer_id: str = Field(..., description="Customer ID (for verification)")
    reason: Optional[str] = Field(None, description="Cancellation reason")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


@tool(name="cancel_booking", description="Cancel an existing appointment", input_schema=CancelBookingArgs, permission="write")
async def cancel_booking(args: CancelBookingArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        idem_key = args.idempotency_key or generate_idempotency_key()

        existing = await check_idempotency(session, ctx.tenant_id, "cancel_booking", idem_key)
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
            return ToolResult(success=False, error="Appointment is already cancelled")

        old_status = appointment.status
        appointment.status = AppointmentStatus.CANCELLED

        status_history = AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=old_status.value if old_status else None,
            to_status=AppointmentStatus.CANCELLED.value,
            changed_by="agent",
        )
        session.add(status_history)

        await session.commit()

        from receptionist.services.notification import NotificationService
        customer_result = await session.execute(
            select(Customer).where(
                Customer.id == appointment.customer_id,
                Customer.tenant_id == ctx.tenant_id,
            )
        )
        customer = customer_result.scalar_one_or_none()
        notification_service = NotificationService(session)
        await notification_service.send_cancellation_notice(appointment, customer.email if customer else None)

        result_data = {
            "appointment_id": appointment.id,
            "status": "cancelled",
            "previous_status": old_status.value if old_status else None,
        }
        await save_idempotency_result(session, ctx.tenant_id, "cancel_booking", idem_key, result_data)
        await session.commit()

        return ToolResult(success=True, data=result_data)
