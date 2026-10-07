from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from receptionist.db.models import Notification, NotificationChannel, NotificationStatus, Appointment
from receptionist.config import get_settings

_settings = get_settings()


class BaseNotificationProvider(ABC):
    @abstractmethod
    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        pass


class EmailProvider(BaseNotificationProvider):
    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        if _settings.dry_run:
            print(f"[DRY RUN] Email to {recipient}: {content[:100]}")
            return True
        return True


class SMSProvider(BaseNotificationProvider):
    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        if _settings.dry_run:
            print(f"[DRY RUN] SMS to {recipient}: {content[:100]}")
            return True
        return True


class WhatsAppProvider(BaseNotificationProvider):
    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        if _settings.dry_run:
            print(f"[DRY RUN] WhatsApp to {recipient}: {content[:100]}")
            return True
        return True


class NotificationService:
    def __init__(self, session):
        self.session = session
        self.providers: dict[NotificationChannel, BaseNotificationProvider] = {
            NotificationChannel.EMAIL: EmailProvider(),
            NotificationChannel.SMS: SMSProvider(),
            NotificationChannel.WHATSAPP: WhatsAppProvider(),
        }

    async def send_notification(
        self,
        tenant_id: str,
        notification_type: str,
        channel: NotificationChannel,
        recipient: str,
        content: str,
        appointment_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> Notification:
        import uuid
        notification = Notification(
            id=f"notif_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            customer_id=customer_id,
            notification_type=notification_type,
            channel=channel,
            recipient=recipient,
            content=content,
            status=NotificationStatus.PENDING,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
        )
        self.session.add(notification)
        await self.session.flush()

        provider = self.providers.get(channel)
        if provider:
            try:
                success = await provider.send(recipient, content)
                notification.status = NotificationStatus.SENT if success else NotificationStatus.FAILED
                if success:
                    notification.sent_at = datetime.now(timezone.utc)
            except Exception as e:
                notification.status = NotificationStatus.FAILED
                notification.error = str(e)

        await self.session.commit()
        return notification

    async def send_appointment_confirmation(self, appointment: Appointment, customer_email: Optional[str] = None):
        content = (
            f"Your appointment is confirmed for "
            f"{appointment.start_time.strftime('%A, %B %d at %I:%M %p')}. "
            f"Appointment ID: {appointment.id}"
        )
        if customer_email:
            await self.send_notification(
                tenant_id=appointment.tenant_id,
                notification_type="appointment_created",
                channel=NotificationChannel.EMAIL,
                recipient=customer_email,
                content=content,
                appointment_id=appointment.id,
                customer_id=appointment.customer_id,
            )

    async def send_appointment_reminder(self, appointment: Appointment, customer_email: Optional[str] = None):
        content = (
            f"Reminder: You have an appointment on "
            f"{appointment.start_time.strftime('%A, %B %d at %I:%M %p')}. "
            f"Appointment ID: {appointment.id}"
        )
        if customer_email:
            await self.send_notification(
                tenant_id=appointment.tenant_id,
                notification_type="appointment_reminder",
                channel=NotificationChannel.EMAIL,
                recipient=customer_email,
                content=content,
                appointment_id=appointment.id,
                customer_id=appointment.customer_id,
            )

    async def send_cancellation_notice(self, appointment: Appointment, customer_email: Optional[str] = None):
        content = (
            f"Your appointment on "
            f"{appointment.start_time.strftime('%A, %B %d at %I:%M %p')} has been cancelled. "
            f"Appointment ID: {appointment.id}"
        )
        if customer_email:
            await self.send_notification(
                tenant_id=appointment.tenant_id,
                notification_type="appointment_cancelled",
                channel=NotificationChannel.EMAIL,
                recipient=customer_email,
                content=content,
                appointment_id=appointment.id,
                customer_id=appointment.customer_id,
            )
