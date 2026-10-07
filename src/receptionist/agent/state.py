from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None


class TimeSlot(BaseModel):
    start_time: str
    end_time: str
    staff_id: Optional[str] = None
    staff_name: Optional[str] = None


class ReceptionistState(BaseModel):
    tenant_id: str = ""
    conversation_id: str = ""
    user_id: Optional[str] = None
    customer_id: Optional[str] = None
    channel: str = "web"

    current_message: str = ""
    conversation_history: list[Message] = Field(default_factory=list)

    intent: Optional[str] = None
    confidence: float = 0.0
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)

    selected_service: Optional[str] = None
    selected_staff: Optional[str] = None
    selected_location: Optional[str] = None
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    timezone: str = "UTC"
    available_slots: list[TimeSlot] = Field(default_factory=list)
    selected_slot: Optional[TimeSlot] = None
    appointment_id: Optional[str] = None

    tool_name: Optional[str] = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    tool_result: Optional[Any] = None

    human_handoff_required: bool = False
    emergency_detected: bool = False

    response: Optional[str] = None
    error: Optional[str] = None

    audit_event_id: Optional[str] = None
    current_node: str = "START"
    execution_status: str = "idle"

    tenant_config: dict[str, Any] = Field(default_factory=dict)
    enabled_tools: list[str] = Field(default_factory=list)
    business_rules: dict[str, Any] = Field(default_factory=dict)

    agent_run_id: Optional[str] = None
    idempotency_key: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
