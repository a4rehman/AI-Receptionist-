from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from receptionist.db.models import (
    AgentEvent,
    AgentRun,
    Appointment,
    AppointmentStatus,
    Conversation,
    HumanHandoff,
)


class AnalyticsService:
    def __init__(self, session):
        self.session = session

    async def get_dashboard_metrics(self, tenant_id: str, days: int = 30) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)

        conv_result = await self.session.execute(
            select(func.count(Conversation.id)).where(
                Conversation.tenant_id == tenant_id,
                Conversation.created_at >= since,
            )
        )
        total_conversations = conv_result.scalar() or 0

        apt_result = await self.session.execute(
            select(func.count(Appointment.id)).where(
                Appointment.tenant_id == tenant_id,
                Appointment.created_at >= since,
            )
        )
        total_appointments = apt_result.scalar() or 0

        cancelled_result = await self.session.execute(
            select(func.count(Appointment.id)).where(
                Appointment.tenant_id == tenant_id,
                Appointment.status == AppointmentStatus.CANCELLED,
                Appointment.created_at >= since,
            )
        )
        cancelled_appointments = cancelled_result.scalar() or 0

        handoff_result = await self.session.execute(
            select(func.count(HumanHandoff.id)).where(
                HumanHandoff.tenant_id == tenant_id,
                HumanHandoff.created_at >= since,
            )
        )
        total_handoffs = handoff_result.scalar() or 0

        run_result = await self.session.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.started_at >= since,
            )
        )
        total_runs = run_result.scalar() or 0

        failed_result = await self.session.execute(
            select(func.count(AgentEvent.id)).where(
                AgentEvent.run_id.in_(
                    select(AgentRun.id).where(AgentRun.tenant_id == tenant_id)
                ),
                AgentEvent.event_type == "TOOL_FAILED",
                AgentEvent.created_at >= since,
            )
        )
        tool_failures = failed_result.scalar() or 0

        return {
            "period_days": days,
            "total_conversations": total_conversations,
            "total_appointments": total_appointments,
            "cancelled_appointments": cancelled_appointments,
            "total_handoffs": total_handoffs,
            "total_agent_runs": total_runs,
            "tool_failures": tool_failures,
            "escalation_rate": round(total_handoffs / max(total_conversations, 1) * 100, 2),
            "cancellation_rate": round(cancelled_appointments / max(total_appointments, 1) * 100, 2),
        }

    async def get_booking_conversion(self, tenant_id: str, days: int = 30) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)

        total_runs = await self.session.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.started_at >= since,
            )
        )
        runs = total_runs.scalar() or 0

        bookings = await self.session.execute(
            select(func.count(Appointment.id)).where(
                Appointment.tenant_id == tenant_id,
                Appointment.created_at >= since,
            )
        )
        booked = bookings.scalar() or 0

        return {
            "total_agent_runs": runs,
            "total_bookings": booked,
            "conversion_rate": round(booked / max(runs, 1) * 100, 2),
        }
