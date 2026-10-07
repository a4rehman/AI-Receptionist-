# Architecture — 100Solutionz AI Receptionist

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CHANNELS                              │
│  Web Chat │ WhatsApp │ SMS │ Email │ Voice (future)         │
└──────────────────────┬──────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Message Adapter │  (channel-specific formatting)
              └────────┬────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   FASTAPI LAYER                              │
│  POST /api/v1/chat                                         │
│  GET  /api/v1/appointments                                  │
│  GET  /api/v1/availability                                  │
│  ... (all tenant-aware)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              LANGGRAPH AGENT ORCHESTRATION                   │
│                                                              │
│  START → LOAD_SESSION → LOAD_TENANT_CONTEXT                 │
│       → INTENT_CLASSIFIER → ENTITY_EXTRACTION                │
│       → SAFETY_CHECK → ROUTER (conditional edges)            │
│       → TOOL_EXECUTION → RESULT_VALIDATION                   │
│       → RESPONSE_GENERATION → SAVE_CONVERSATION              │
│       → UPDATE_AGENT_STATE → END                            │
│                                                              │
│  Intents: FAQ │ BOOKING │ AVAILABILITY │ RESCHEDULE │        │
│           CANCEL │ LOOKUP │ HANDOFF │ EMERGENCY │ GENERAL    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     TOOL LAYER                               │
│  customer_tools │ staff_tools │ service_tools                │
│  availability_tools │ booking_tools │ cancellation_tools     │
│  reschedule_tools │ notification_tools │ faq_tools           │
│  business_tools │ human_handoff_tools                        │
│                                                              │
│  All tools: validate tenant_id, use Pydantic schemas,       │
│  enforce business rules, write audit logs                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   REPOSITORY LAYER                           │
│  Tenant-scoped queries only (tenant_id enforced)             │
│  SQLAlchemy 2.0 async + connection pooling                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   TiDB CLOUD                                 │
│  MySQL-compatible, distributed, HTAP                         │
└─────────────────────────────────────────────────────────────┘
```

## 2. Multi-Tenant Architecture

### Tenant Context
Every request carries `tenant_id`. The context flows:
```
API Request → TenantContext → Agent State → Tool Calls → Repository → SQL WHERE tenant_id = ?
```

### Tenant Isolation Rules
1. Every tenant-scoped table has `tenant_id` column (PK composite or indexed).
2. Repository methods REQUIRE `tenant_id` parameter.
3. No cross-tenant queries allowed at any layer.
4. Test: `test_tenant_isolation` verifies Tenant A cannot access Tenant B data.

### Tenant Configuration
```json
{
  "tenant_id": "clinic_001",
  "business_type": "dental_clinic",
  "business_name": "ABC Dental",
  "timezone": "America/New_York",
  "currency": "USD",
  "booking_enabled": true,
  "cancellation_policy": {"min_hours_notice": 24},
  "notification_settings": {"email": true, "sms": false, "whatsapp": false},
  "ai_personality": "professional_friendly",
  "emergency_instructions": "Call 911 immediately...",
  "enabled_tools": ["get_services", "get_availability", "create_booking", ...]
}
```

## 3. LangGraph Agent Design

### State Schema (Pydantic)
```python
class ReceptionistState(BaseModel):
    # Context
    tenant_id: str
    conversation_id: str
    user_id: Optional[str] = None
    customer_id: Optional[str] = None
    channel: str = "web"
    
    # Input
    current_message: str
    conversation_history: List[Message] = []
    
    # Classification
    intent: Optional[str] = None
    confidence: float = 0.0
    extracted_entities: Dict[str, Any] = {}
    missing_information: List[str] = []
    
    # Booking flow
    selected_service: Optional[str] = None
    selected_staff: Optional[str] = None
    selected_location: Optional[str] = None
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    timezone: str = "UTC"
    available_slots: List[Slot] = []
    selected_slot: Optional[Slot] = None
    appointment_id: Optional[str] = None
    
    # Tool execution
    tool_name: Optional[str] = None
    tool_arguments: Dict[str, Any] = {}
    tool_result: Optional[Any] = None
    
    # Safety
    human_handoff_required: bool = False
    emergency_detected: bool = False
    
    # Output
    response: Optional[str] = None
    error: Optional[str] = None
    
    # Observability
    audit_event_id: Optional[str] = None
    current_node: str = "START"
    execution_status: str = "idle"
```

### Graph Flow
```
START
  ↓
LOAD_SESSION — load conversation history, customer context
  ↓
LOAD_TENANT_CONTEXT — load tenant config, business rules, enabled tools
  ↓
INTENT_CLASSIFIER — classify user message → intent + confidence
  ↓
ENTITY_EXTRACTION — extract dates, times, names, services, etc.
  ↓
SAFETY_CHECK — detect emergencies, prompt injection, PII
  ↓
ROUTER — conditional edge based on intent
  ├── FAQ → faq_tools → RESPONSE_GENERATION
  ├── SERVICES → service_tools → RESPONSE_GENERATION
  ├── BUSINESS_INFO → business_tools → RESPONSE_GENERATION
  ├── AVAILABILITY → availability_tools → RESPONSE_GENERATION
  ├── BOOKING → booking flow (multi-turn) → booking_tools → RESPONSE_GENERATION
  ├── RESCHEDULE → reschedule flow → reschedule_tools → RESPONSE_GENERATION
  ├── CANCEL → cancel flow → cancellation_tools → RESPONSE_GENERATION
  ├── APPOINTMENT_LOOKUP → customer_tools → RESPONSE_GENERATION
  ├── CUSTOMER_LOOKUP → customer_tools → RESPONSE_GENERATION
  ├── HUMAN_HANDOFF → human_handoff_tools → RESPONSE_GENERATION
  ├── EMERGENCY → emergency policy → HUMAN_HANDOFF
  └── GENERAL_CONVERSATION → RESPONSE_GENERATION
  ↓
RESULT_VALIDATION — verify tool succeeded before confirming
  ↓
RESPONSE_GENERATION — generate natural language response
  ↓
SAVE_CONVERSATION — persist messages + agent run
  ↓
UPDATE_AGENT_STATE — update execution status
  ↓
END
```

### Conditional Edges
- After INTENT_CLASSIFIER: route to intent-specific node
- After ENTITY_EXTRACTION: if missing info → ASK_MISSING_INFO → back to LOAD_SESSION
- After TOOL_EXECUTION: if tool failed → ERROR_HANDLING → RESPONSE_GENERATION
- After BOOKING: if confirmed → BOOKING_TOOL → RESPONSE_GENERATION; if cancelled → END

## 4. Tool Architecture

### Tool Registry Pattern
```python
@tool(name="get_availability", permission="read", description="...")
async def get_availability(args: AvailabilityArgs, context: ToolContext) -> ToolResult:
    # 1. Validate tenant_id
    # 2. Validate input schema (Pydantic)
    # 3. Check business rules
    # 4. Execute query
    # 5. Write audit log
    # 6. Return result
```

### Tool Permissions
| Permission | Tools |
|-----------|-------|
| read | get_business_info, get_services, get_staff, get_availability, get_customer, get_appointments, get_faq |
| write | create_customer, create_booking, update_booking, cancel_booking, create_handoff |

### Tool Validation
- Pydantic input schemas for every tool
- Tenant ID validated against context
- Business rules checked before execution
- Idempotency keys for write operations

## 5. Availability Engine

### Algorithm
```
Input: tenant_id, staff_id, service_id, date, timezone
Output: List[TimeSlot]

1. Get staff working hours for the day
2. Get business hours for the day
3. Get holidays (skip if holiday)
4. Get existing appointments for staff on that date
5. Get service duration + buffer time
6. Generate candidate slots within working hours
7. Remove slots that overlap with existing appointments
8. Remove slots that violate booking rules (min notice, max horizon)
9. Return available slots
```

### Concurrency Protection
- `SELECT ... FOR UPDATE` on staff schedule during booking
- Idempotency key prevents duplicate bookings
- Transaction wraps availability check + booking insert

## 6. Booking Engine

### Transaction Flow
```python
async with db.transaction():
    # 1. Re-check availability (FOR UPDATE)
    slots = await availability_service.check(staff_id, date, for_update=True)
    if selected_slot not in slots:
        raise BookingConflictError()
    
    # 2. Create appointment
    appointment = await booking_repo.create(...)
    
    # 3. Create audit event
    await audit_service.log(...)
    
    # 4. Queue notification (async)
    await notification_service.queue_confirmation(appointment)
    
    return appointment
```

### Idempotency
- Client generates `booking_request_id` (UUID)
- Stored in `idempotency_keys` table
- Same key → return original result, no duplicate

## 7. Database Schema (Core Tables)

```
tenants (id, business_type, business_name, timezone, currency, ...)
tenant_settings (tenant_id, key, value, ...)
locations (id, tenant_id, name, address, phone, ...)
staff (id, tenant_id, name, role, specialization, department, email, phone, ...)
staff_schedules (id, staff_id, day_of_week, start_time, end_time, ...)
services (id, tenant_id, name, description, duration_minutes, price, ...)
staff_services (staff_id, service_id, ...)
customers (id, tenant_id, first_name, last_name, email, phone, ...)
appointments (id, tenant_id, customer_id, staff_id, service_id, location_id, 
              start_time, end_time, status, idempotency_key, ...)
conversations (id, tenant_id, customer_id, channel, status, ...)
messages (id, conversation_id, role, content, created_at, ...)
agent_runs (id, conversation_id, status, started_at, completed_at, ...)
agent_events (id, run_id, event_type, node_name, tool_name, status, ...)
tool_calls (id, run_id, tool_name, arguments, result, status, ...)
human_handoffs (id, tenant_id, conversation_id, reason, priority, status, ...)
notifications (id, tenant_id, type, channel, recipient, content, status, ...)
audit_logs (id, tenant_id, action, entity_type, entity_id, actor, ...)
faqs (id, tenant_id, question, answer, category, ...)
idempotency_keys (id, tenant_id, operation, key, result, created_at, ...)
```

## 8. LLM Provider Abstraction

```python
class BaseLLMProvider(ABC):
    async def complete(self, messages, **kwargs) -> str: ...
    async def structured_complete(self, messages, schema, **kwargs) -> dict: ...

class OpenAIProvider(BaseLLMProvider): ...
class AnthropicProvider(BaseLLMProvider): ...
class AzureOpenAIProvider(BaseLLMProvider): ...
class MockLLMProvider(BaseLLMProvider): ...  # for testing
class RuleBasedClassifier: ...  # fallback intent classifier
```

## 9. Observability

### Structured Logging
```json
{
  "timestamp": "2026-10-08T10:30:00Z",
  "level": "INFO",
  "trace_id": "abc123",
  "run_id": "run_456",
  "tenant_id": "clinic_001",
  "conversation_id": "conv_789",
  "node": "AVAILABILITY_CHECK",
  "tool": "get_availability",
  "duration_ms": 421,
  "message": "Availability check completed"
}
```

### Agent Event Stream
Events stored in `agent_events` table, consumed by dashboard via polling or WebSocket.

### LangSmith Compatibility
- Trace structure compatible with LangSmith format
- Can export to LangSmith via callback handler

## 10. Security Architecture

| Layer | Measures |
|-------|---------|
| API | API key + JWT, rate limiting, input validation |
| Agent | Prompt injection defense, tool permission enforcement |
| Database | Tenant isolation, parameterized queries, encrypted secrets |
| Notifications | Provider abstraction, dry-run mode, opt-out respect |
| Audit | Immutable audit log, PII redaction |

### Prompt Injection Defense
1. System prompt clearly separates instructions from data
2. Retrieved documents wrapped in `<untrusted>` tags
3. Tool descriptions include injection warnings
4. User input never interpreted as system commands
5. Output filtering for sensitive patterns

## 11. Deployment Architecture

```
┌─────────────────────────────────────────────┐
│                  Docker Compose              │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   API    │  │ Worker   │  │Dashboard │  │
│  │ FastAPI  │  │Reminders │  │Streamlit │  │
│  │  :8000   │  │  :8001   │  │  :8501   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │        │
│       └──────────────┼──────────────┘        │
│                      │                       │
│              ┌───────▼───────┐               │
│              │   TiDB Cloud   │               │
│              └───────────────┘               │
└─────────────────────────────────────────────┘
```

## 12. Development Strategy

### Vertical Slices
1. **Slice 1:** Config + DB + Models + Migrations + Repository
2. **Slice 2:** Agent state + Graph + Rule-based classifier + Mock tools
3. **Slice 3:** Real tools (customer, staff, service, availability)
4. **Slice 4:** Booking engine + API + Basic dashboard
5. **Slice 5:** Advanced features (handoff, notifications, RAG)

### Testing Strategy
- Unit: pytest, mocked DB
- Integration: SQLite in-memory (TiDB-compatible SQL)
- E2E: Full flow with mock LLM
- Concurrency: asyncio tasks for double-booking tests
