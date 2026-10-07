# Implementation Plan — 100Solutionz AI Receptionist

## Phase 1: Foundation (Days 1-2)

### 1.1 Project Scaffolding
- [ ] `pyproject.toml` with all dependencies
- [ ] `.env.example` with all config vars
- [ ] `src/` package structure
- [ ] `config.py` — Pydantic settings
- [ ] `logging_config.py` — structured JSON logging

### 1.2 Database Layer
- [ ] SQLAlchemy 2.0 async engine setup
- [ ] All model definitions (20+ tables)
- [ ] Alembic migration: initial schema
- [ ] Repository base class with tenant enforcement
- [ ] Connection pooling config

### 1.3 LLM Provider Abstraction
- [ ] `BaseLLMProvider` interface
- [ ] `MockLLMProvider` for dev/testing
- [ ] `OpenAIProvider` implementation
- [ ] `RuleBasedIntentClassifier` (fallback)

### 1.4 Core Utilities
- [ ] Date/time parsing (relative dates, timezones)
- [ ] PII redaction for logs
- [ ] Idempotency key generation
- [ ] Tenant context manager

## Phase 2: Agent Core (Days 3-4)

### 2.1 LangGraph State
- [ ] `ReceptionistState` Pydantic model
- [ ] State serialization/deserialization

### 2.2 Graph Nodes
- [ ] `load_session` node
- [ ] `load_tenant_context` node
- [ ] `intent_classifier` node
- [ ] `entity_extraction` node
- [ ] `safety_check` node
- [ ] `router` conditional edges
- [ ] `tool_execution` node
- [ ] `result_validation` node
- [ ] `response_generation` node
- [ ] `save_conversation` node
- [ ] `update_agent_state` node

### 2.3 Tool Registry
- [ ] Tool decorator + registry pattern
- [ ] Tool permission enforcement
- [ ] Tool input validation (Pydantic)
- [ ] Tool audit logging

### 2.4 Conversation Persistence
- [ ] Save messages to DB
- [ ] Save agent runs + events
- [ ] Load conversation history

## Phase 3: Business Tools (Days 5-6)

### 3.1 Customer Tools
- [ ] `get_customer`
- [ ] `find_customer_by_phone`
- [ ] `find_customer_by_email`
- [ ] `create_customer`
- [ ] `update_customer`
- [ ] `get_customer_appointments`

### 3.2 Staff Tools
- [ ] `list_staff`
- [ ] `search_staff`
- [ ] `get_staff_services`
- [ ] `get_staff_schedule`

### 3.3 Service Tools
- [ ] `list_services`
- [ ] `search_services`
- [ ] `get_service_price`
- [ ] `get_service_duration`

### 3.4 Availability Engine
- [ ] Working hours calculation
- [ ] Holiday checking
- [ ] Existing appointment exclusion
- [ ] Buffer time handling
- [ ] Booking rule enforcement
- [ ] Slot generation algorithm

### 3.5 Booking Engine
- [ ] Transactional booking with FOR UPDATE
- [ ] Idempotency key support
- [ ] Double-booking prevention
- [ ] Audit logging
- [ ] Confirmation notification trigger

### 3.6 Cancellation + Reschedule
- [ ] Cancel with policy check
- [ ] Reschedule with availability re-check
- [ ] Both with idempotency

## Phase 4: API + Dashboard (Days 7-8)

### 4.1 FastAPI Endpoints
- [ ] `POST /api/v1/chat`
- [ ] `GET /api/v1/appointments`
- [ ] `GET /api/v1/appointments/{id}`
- [ ] `PATCH /api/v1/appointments/{id}`
- [ ] `DELETE /api/v1/appointments/{id}`
- [ ] `GET /api/v1/availability`
- [ ] `GET /api/v1/services`
- [ ] `GET /api/v1/staff`
- [ ] `GET /api/v1/customers`
- [ ] `POST /api/v1/handoff`
- [ ] `GET /api/v1/agent-runs`
- [ ] `GET /api/v1/agent-events`
- [ ] Auth middleware (API key)
- [ ] Rate limiting

### 4.2 Streamlit Dashboard
- [ ] Dashboard overview (KPIs)
- [ ] Live agent runs monitor
- [ ] Conversations list
- [ ] Appointments management
- [ ] Customers view
- [ ] Staff/Services config
- [ ] Knowledge base (FAQ)
- [ ] Handoffs queue
- [ ] Analytics page

## Phase 5: Advanced Features (Days 9-10)

### 5.1 Human Handoff
- [ ] Handoff creation tool
- [ ] Handoff queue in dashboard
- [ ] Take over / reply / close / return to AI

### 5.2 Notifications
- [ ] Provider abstraction (Email, SMS, WhatsApp)
- [ ] Email templates (confirmation, reminder, cancellation)
- [ ] Dry-run mode for development
- [ ] Notification logging

### 5.3 FAQ / RAG
- [ ] FAQ retrieval tool
- [ ] Vector store abstraction
- [ ] Document ingestion (basic)
- [ ] Tenant-scoped retrieval

### 5.4 Reminders
- [ ] APScheduler integration
- [ ] Configurable reminder schedule
- [ ] Reminder notification dispatch

### 5.5 Analytics
- [ ] Conversation metrics
- [ ] Booking conversion
- [ ] Tool failure rates
- [ ] Escalation rates

## Phase 6: Production Hardening (Days 11-12)

### 6.1 Security
- [ ] JWT authentication
- [ ] RBAC implementation
- [ ] Rate limiting
- [ ] Input sanitization
- [ ] Security headers

### 6.2 Testing
- [ ] Unit tests (all tools, availability, booking)
- [ ] Integration tests (DB, agent flow)
- [ ] Concurrency tests (double-booking)
- [ ] Tenant isolation tests
- [ ] E2E scenario tests (all 11 scenarios)

### 6.3 Deployment
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] Production config docs
- [ ] Migration runbook

### 6.4 Documentation
- [ ] README.md
- [ ] All docs/ files
- [ ] API documentation (auto-generated)

## File Structure

```
ai_receptionist/
├── pyproject.toml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── docs/
│   ├── REPOSITORY_AUDIT.md
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── langgraph.md
│   ├── database.md
│   ├── tools.md
│   ├── booking-engine.md
│   ├── multi-tenancy.md
│   ├── security.md
│   ├── observability.md
│   ├── deployment.md
│   ├── healthcare-safety.md
│   └── testing.md
├── migrations/
│   └── versions/
├── src/
│   └── receptionist/
│       ├── __init__.py
│       ├── config.py
│       ├── logging_config.py
│       ├── main.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── models.py
│       │   ├── repository.py
│       │   └── tenant.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── graph.py
│       │   ├── state.py
│       │   ├── nodes.py
│       │   ├── router.py
│       │   └── policies.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   ├── customer_tools.py
│       │   ├── staff_tools.py
│       │   ├── service_tools.py
│       │   ├── availability_tools.py
│       │   ├── booking_tools.py
│       │   ├── cancellation_tools.py
│       │   ├── reschedule_tools.py
│       │   ├── notification_tools.py
│       │   ├── faq_tools.py
│       │   ├── business_tools.py
│       │   └── human_handoff_tools.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── availability.py
│       │   ├── booking.py
│       │   ├── notification.py
│       │   └── audit.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   └── mock_provider.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   ├── schemas.py
│       │   └── middleware.py
│       ├── dashboard/
│       │   ├── __init__.py
│       │   └── app.py
│       └── utils/
│           ├── __init__.py
│           ├── datetime_utils.py
│           ├── pii.py
│           └── idempotency.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_availability.py
    ├── test_booking.py
    ├── test_cancellation.py
    ├── test_reschedule.py
    ├── test_tenant_isolation.py
    ├── test_intent_classifier.py
    ├── test_datetime_utils.py
    ├── test_tools.py
    └── e2e/
        ├── test_dental_booking.py
        ├── test_hospital_booking.py
        ├── test_salon_booking.py
        ├── test_restaurant_reservation.py
        ├── test_hotel_reservation.py
        ├── test_appointment_lookup.py
        ├── test_reschedule.py
        ├── test_cancellation.py
        ├── test_human_handoff.py
        └── test_emergency.py
```

## Immediate Next Steps

1. Create `pyproject.toml` with dependencies
2. Create `.env.example`
3. Create `config.py`
4. Create database models
5. Create initial Alembic migration
6. Create repository base
7. Begin agent implementation
