from typing import ClassVar

import pytest

from receptionist.config import get_settings
from receptionist.db.models import NotificationChannel, NotificationStatus
from receptionist.services.notification import (
    BaseNotificationProvider,
    EmailProvider,
    NotificationService,
    SMSProvider,
    WhatsAppProvider,
)


@pytest.fixture
def apply_env(monkeypatch):
    def _apply(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, str(value))
        get_settings.cache_clear()
        return get_settings()

    yield _apply
    get_settings.cache_clear()


class StubProvider(BaseNotificationProvider):
    channel = "stub"

    def __init__(self, result: bool = True, error: Exception | None = None):
        self.result = result
        self.error = error
        self.sent: list[tuple[str, str, dict]] = []

    async def send(self, recipient: str, content: str, **kwargs) -> bool:
        if self.error is not None:
            raise self.error
        self.sent.append((recipient, content, kwargs))
        return self.result


class FakeResponse:
    def __init__(self, status_code: int = 201):
        self.status_code = status_code
        self.raised = False

    def raise_for_status(self):
        self.raised = True


class FakeAsyncClient:
    instances: ClassVar[list["FakeAsyncClient"]] = []

    def __init__(self, *args, **kwargs):
        self.posts: list[tuple[str, dict]] = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse()


@pytest.fixture
def fake_httpx(monkeypatch):
    from receptionist.services import notification as module

    FakeAsyncClient.instances = []
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.mark.asyncio
async def test_email_dry_run_returns_true_without_config(apply_env):
    apply_env(DRY_RUN="true", SMTP_HOST="")
    assert await EmailProvider().send("a@example.com", "hello") is True


@pytest.mark.asyncio
async def test_email_unconfigured_is_failure(apply_env):
    apply_env(DRY_RUN="false", SMTP_HOST="", SMTP_USER="", SMTP_PASSWORD="")
    assert await EmailProvider().send("a@example.com", "hello") is False


@pytest.mark.asyncio
async def test_email_sends_via_smtp(apply_env, monkeypatch):
    apply_env(
        DRY_RUN="false",
        SMTP_HOST="smtp.example.com",
        SMTP_USER="user",
        SMTP_PASSWORD="pass",
        SMTP_FROM="from@example.com",
    )
    captured = {}

    def fake_send_sync(self, settings, recipient, subject, content):
        captured.update(
            host=settings.smtp_host, recipient=recipient, subject=subject, content=content
        )

    monkeypatch.setattr(EmailProvider, "_send_sync", fake_send_sync)

    assert await EmailProvider().send("a@example.com", "hello", subject="Hi") is True
    assert captured["host"] == "smtp.example.com"
    assert captured["recipient"] == "a@example.com"
    assert captured["subject"] == "Hi"


@pytest.mark.asyncio
async def test_sms_unconfigured_is_failure(apply_env):
    apply_env(DRY_RUN="false", TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="")
    assert await SMSProvider().send("+15551234567", "hi") is False


@pytest.mark.asyncio
async def test_sms_sends_via_twilio(apply_env, fake_httpx):
    apply_env(
        DRY_RUN="false",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="secret",
        TWILIO_FROM_NUMBER="+15550000000",
    )

    assert await SMSProvider().send("+15551234567", "hi") is True

    client = fake_httpx.instances[0]
    url, kwargs = client.posts[0]
    assert "AC123" in url and url.endswith("Messages.json")
    assert kwargs["data"]["To"] == "+15551234567"
    assert kwargs["data"]["From"] == "+15550000000"
    assert kwargs["auth"] == ("AC123", "secret")


@pytest.mark.asyncio
async def test_whatsapp_sends_via_cloud_api(apply_env, fake_httpx):
    apply_env(
        DRY_RUN="false",
        WHATSAPP_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="999",
        WHATSAPP_API_URL="https://graph.facebook.com/v18.0",
    )

    assert await WhatsAppProvider().send("+15551234567", "hi") is True

    url, kwargs = fake_httpx.instances[0].posts[0]
    assert url == "https://graph.facebook.com/v18.0/999/messages"
    assert kwargs["headers"]["Authorization"] == "Bearer token"
    assert kwargs["json"]["to"] == "+15551234567"
    assert kwargs["json"]["text"]["body"] == "hi"


@pytest.mark.asyncio
async def test_service_marks_sent(db_session):
    provider = StubProvider(result=True)
    service = NotificationService(db_session, providers={NotificationChannel.EMAIL: provider})

    notification = await service.send_notification(
        tenant_id="t1",
        notification_type="appointment_created",
        channel=NotificationChannel.EMAIL,
        recipient="a@example.com",
        content="hello",
    )

    assert notification.status == NotificationStatus.SENT
    assert notification.sent_at is not None
    assert provider.sent[0][0] == "a@example.com"


@pytest.mark.asyncio
async def test_service_marks_failed_when_unconfigured(db_session):
    provider = StubProvider(result=False)
    service = NotificationService(db_session, providers={NotificationChannel.EMAIL: provider})

    notification = await service.send_notification(
        tenant_id="t1",
        notification_type="appointment_created",
        channel=NotificationChannel.EMAIL,
        recipient="a@example.com",
        content="hello",
    )

    assert notification.status == NotificationStatus.FAILED
    assert notification.error


@pytest.mark.asyncio
async def test_service_records_provider_exception(db_session):
    provider = StubProvider(error=RuntimeError("smtp down"))
    service = NotificationService(db_session, providers={NotificationChannel.EMAIL: provider})

    notification = await service.send_notification(
        tenant_id="t1",
        notification_type="appointment_created",
        channel=NotificationChannel.EMAIL,
        recipient="a@example.com",
        content="hello",
    )

    assert notification.status == NotificationStatus.FAILED
    assert notification.error == "smtp down"


@pytest.mark.asyncio
async def test_service_fails_for_missing_provider(db_session):
    service = NotificationService(db_session, providers={})

    notification = await service.send_notification(
        tenant_id="t1",
        notification_type="appointment_created",
        channel=NotificationChannel.EMAIL,
        recipient="a@example.com",
        content="hello",
    )

    assert notification.status == NotificationStatus.FAILED
    assert "No provider" in notification.error
