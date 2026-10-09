from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime | None = None


class TimeSlot(BaseModel):
    start_time: str
    end_time: str
    staff_id: str | None = None
    staff_name: str | None = None


class ReceptionistState(BaseModel):
    tenant_id: str = ""
    conversation_id: str = ""
    user_id: str | None = None
    customer_id: str | None = None
    channel: str = "web"

    current_message: str = ""
    conversation_history: list[Message] = Field(default_factory=list)

    intent: str | None = None
    confidence: float = 0.0
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)

    selected_service: str | None = None
    selected_staff: str | None = None
    selected_location: str | None = None
    requested_date: str | None = None
    requested_time: str | None = None
    timezone: str = "UTC"
    available_slots: list[TimeSlot] = Field(default_factory=list)
    selected_slot: TimeSlot | None = None
    appointment_id: str | None = None

    tool_name: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    tool_result: Any | None = None

    human_handoff_required: bool = False
    emergency_detected: bool = False

    response: str | None = None
    error: str | None = None

    audit_event_id: str | None = None
    current_node: str = "START"
    execution_status: str = "idle"

    tenant_config: dict[str, Any] = Field(default_factory=dict)
    enabled_tools: list[str] = Field(default_factory=list)
    business_rules: dict[str, Any] = Field(default_factory=dict)

    agent_run_id: str | None = None
    idempotency_key: str | None = None

    class Config:
        arbitrary_types_allowed = True
