import asyncio
import smtplib
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

import httpx
import structlog

from receptionist.config import get_settings
from receptionist.db.models import (
    Appointment,
    Notification,
    NotificationChannel,
    NotificationStatus,
)

logger = structlog.get_logger()


class BaseNotificationProvider(ABC):
    channel: str = "base"

    @property
    def configured(self) -> bool:
        return False

    @abstractmethod
    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        """Deliver a message. Return True on success, False when unconfigured.

        Raise on transport errors so the caller can record the failure reason.
        """


class EmailProvider(BaseNotificationProvider):
    channel = "email"

    @property
    def configured(self) -> bool:
        return bool(get_settings().smtp_host)

    async def send(self, recipient: str, content: str, subject: Optional[str] = None, **kwargs) -> bool:
        settings = get_settings()
        subject = subject or "Appointment Notification"
        if settings.dry_run:
            logger.info(
                "notification_dry_run",
                channel=self.channel,
                recipient=recipient,
                preview=content[:100],
            )
            return True
        if not self.configured:
            logger.error("notification_provider_not_configured", channel=self.channel)
            return False
        await asyncio.to_thread(self._send_sync, settings, recipient, subject, content)
        return True

    @staticmethod
    def _send_sync(settings, recipient: str, subject: str, content: str) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from or settings.smtp_user
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(content)

        host, port = settings.smtp_host, settings.smtp_port
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                logger.warning("smtp_starttls_unsupported", host=host)
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)


class SMSProvider(BaseNotificationProvider):
    channel = "sms"

    @property
    def configured(self) -> bool:
        settings = get_settings()
        return bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
        )

    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        settings = get_settings()
        if settings.dry_run:
            logger.info(
                "notification_dry_run",
                channel=self.channel,
                recipient=recipient,
                preview=content[:100],
            )
            return True
        if not self.configured:
            logger.error("notification_provider_not_configured", channel=self.channel)
            return False

        url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.twilio_account_sid}/Messages.json"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                data={
                    "From": settings.twilio_from_number,
                    "To": recipient,
                    "Body": content,
                },
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            response.raise_for_status()
        return True


class WhatsAppProvider(BaseNotificationProvider):
    channel = "whatsapp"

    @property
    def configured(self) -> bool:
        settings = get_settings()
        return bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)

    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        settings = get_settings()
        if settings.dry_run:
            logger.info(
                "notification_dry_run",
                channel=self.channel,
                recipient=recipient,
                preview=content[:100],
            )
            return True
        if not self.configured:
            logger.error("notification_provider_not_configured", channel=self.channel)
            return False

        url = f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": content},
                },
            )
            response.raise_for_status()
        return True


class NotificationService:
    def __init__(self, session, providers: Optional[dict[NotificationChannel, BaseNotificationProvider]] = None):
        self.session = session
        self.providers = providers if providers is not None else {
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
        subject: Optional[str] = None,
    ) -> Notification:
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
        if provider is None:
            notification.status = NotificationStatus.FAILED
            notification.error = f"No provider for channel '{channel}'"
        else:
            try:
                success = await provider.send(recipient, content, subject=subject)
                notification.status = NotificationStatus.SENT if success else NotificationStatus.FAILED
                if success:
                    notification.sent_at = datetime.now(timezone.utc)
                else:
                    notification.error = f"{channel} provider is not configured"
            except Exception as e:
                logger.error(
                    "notification_send_failed",
                    channel=str(channel),
                    recipient=recipient,
                    error=str(e),
                )
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
                subject="Your appointment is confirmed",
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
                subject="Appointment reminder",
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
                subject="Your appointment has been cancelled",
            )
