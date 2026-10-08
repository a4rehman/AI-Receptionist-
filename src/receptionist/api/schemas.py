from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (creates new if not provided)")
    message: str = Field(..., description="User message")
    channel: str = Field("web", description="Channel (web, whatsapp, sms, email)")
    customer_id: Optional[str] = Field(None, description="Known customer ID")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key for safe retries")


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    status: str
    intent: Optional[str] = None
    available_actions: list[str] = Field(default_factory=list)


class AppointmentResponse(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    staff_id: Optional[str] = None
    service_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    status: str


class AvailabilityRequest(BaseModel):
    tenant_id: str
    service_id: str
    date: str
    staff_id: Optional[str] = None
    timezone: str = "UTC"


class AvailabilityResponse(BaseModel):
    slots: list[dict[str, Any]]


class ServiceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: Optional[float] = None
    currency: str = "USD"


class StaffResponse(BaseModel):
    id: str
    name: str
    role: Optional[str] = None
    specialization: Optional[str] = None
    department: Optional[str] = None


class CustomerResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class HandoffRequest(BaseModel):
    tenant_id: str
    conversation_id: str
    reason: str
    priority: str = "medium"
    customer_id: Optional[str] = None


class HandoffResponse(BaseModel):
    id: str
    status: str
    priority: str


class AgentRunResponse(BaseModel):
    id: str
    conversation_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None


class AgentEventResponse(BaseModel):
    id: int
    run_id: str
    event_type: str
    node_name: Optional[str] = None
    tool_name: Optional[str] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
