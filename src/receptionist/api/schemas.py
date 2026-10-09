from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    tenant_id: str | None = Field(None, description="Tenant identifier (derived from API key if omitted; must match it if provided)")
    conversation_id: str | None = Field(None, description="Conversation ID (creates new if not provided)")
    message: str = Field(..., description="User message")
    channel: str = Field("web", description="Channel (web, whatsapp, sms, email)")
    customer_id: str | None = Field(None, description="Known customer ID")
    idempotency_key: str | None = Field(None, description="Optional idempotency key for safe retries")


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    status: str
    intent: str | None = None
    available_actions: list[str] = Field(default_factory=list)


class AppointmentResponse(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    staff_id: str | None = None
    service_id: str | None = None
    start_time: datetime
    end_time: datetime
    status: str


class AvailabilityRequest(BaseModel):
    tenant_id: str
    service_id: str
    date: str
    staff_id: str | None = None
    timezone: str = "UTC"


class AvailabilityResponse(BaseModel):
    slots: list[dict[str, Any]]


class ServiceResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    duration_minutes: int
    price: float | None = None
    currency: str = "USD"


class StaffResponse(BaseModel):
    id: str
    name: str
    role: str | None = None
    specialization: str | None = None
    department: str | None = None


class CustomerResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None


class HandoffRequest(BaseModel):
    tenant_id: str | None = None
    conversation_id: str
    reason: str
    priority: str = "medium"
    customer_id: str | None = None


class HandoffResponse(BaseModel):
    id: str
    status: str
    priority: str


class AgentRunResponse(BaseModel):
    id: str
    conversation_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None


class AgentEventResponse(BaseModel):
    id: int
    run_id: str
    event_type: str
    node_name: str | None = None
    tool_name: str | None = None
    status: str | None = None
    duration_ms: int | None = None
    created_at: datetime
