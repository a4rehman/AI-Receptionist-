from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from receptionist.db.models import Appointment, AppointmentStatus
from receptionist.services.notification import NotificationService


class ReminderService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.scheduler = AsyncIOScheduler()
        self.notification_service: NotificationService | None = None

    def start(self):
        self.scheduler.start()

    def shutdown(self):
        self.scheduler.shutdown()

    async def schedule_reminders(self, appointment: Appointment, reminder_hours: list[int] | None = None):
        if reminder_hours is None:
            reminder_hours = [24, 2]

        async with self.session_factory() as session:
            self.notification_service = NotificationService(session)
            for hours in reminder_hours:
                reminder_time = appointment.start_time - timedelta(hours=hours)
                if reminder_time > datetime.now(UTC):
                    self.scheduler.add_job(
                        self._send_reminder,
                        trigger=DateTrigger(run_date=reminder_time),
                        args=[appointment.id, hours],
                        id=f"reminder_{appointment.id}_{hours}h",
                        replace_existing=True,
                    )

    async def _send_reminder(self, appointment_id: str, hours_before: int):
        async with self.session_factory() as session:
            result = await session.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            appointment = result.scalar_one_or_none()
            if not appointment or appointment.status != AppointmentStatus.CONFIRMED:
                return

            from receptionist.db.models import Customer
            customer_result = await session.execute(
                select(Customer).where(Customer.id == appointment.customer_id)
            )
            customer = customer_result.scalar_one_or_none()

            notification_service = NotificationService(session)
            await notification_service.send_appointment_reminder(
                appointment,
                customer.email if customer else None,
            )

    async def get_pending_reminders(self, tenant_id: str):
        async with self.session_factory() as session:
            result = await session.execute(
                select(Appointment).where(
                    Appointment.tenant_id == tenant_id,
                    Appointment.status == AppointmentStatus.CONFIRMED,
                    Appointment.start_time > datetime.now(UTC),
                ).order_by(Appointment.start_time)
            )
            return result.scalars().all()
