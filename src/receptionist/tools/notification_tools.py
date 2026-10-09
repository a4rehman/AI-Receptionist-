from pydantic import BaseModel, Field

from receptionist.tools.registry import ToolContext, ToolResult, tool


class SendNotificationArgs(BaseModel):
    channel: str = Field(..., description="Notification channel: email, sms, whatsapp")
    recipient: str = Field(..., description="Recipient address/phone")
    content: str = Field(..., description="Notification content")
    notification_type: str = Field("general", description="Type of notification")


@tool(name="send_notification", description="Send a notification to a customer", input_schema=SendNotificationArgs, permission="write")
async def send_notification(args: SendNotificationArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    from receptionist.db.models import NotificationChannel
    from receptionist.services.notification import NotificationService

    try:
        channel = NotificationChannel(args.channel)
    except ValueError:
        return ToolResult(success=False, error=f"Invalid channel: {args.channel}")

    async with async_session_factory() as session:
        service = NotificationService(session)
        notification = await service.send_notification(
            tenant_id=ctx.tenant_id,
            notification_type=args.notification_type,
            channel=channel,
            recipient=args.recipient,
            content=args.content,
        )
        return ToolResult(success=True, data={
            "notification_id": notification.id,
            "status": notification.status.value,
            "channel": args.channel,
        })
