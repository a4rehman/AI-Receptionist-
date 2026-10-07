# LangGraph Agent Documentation

## State Machine

The receptionist uses a LangGraph state machine with the following nodes:

```
START → LOAD_SESSION → LOAD_TENANT_CONTEXT → INTENT_CLASSIFIER
  → ENTITY_EXTRACTION → SAFETY_CHECK → ROUTER
  → [intent-specific handler] → SAVE_CONVERSATION
  → UPDATE_AGENT_STATE → END
```

## State Schema

See `src/receptionist/agent/state.py` for the full `ReceptionistState` Pydantic model.

## Intent Routing

The router classifies messages into intents:
- `booking` — Create new appointment
- `availability` — Check available slots
- `reschedule` — Move existing appointment
- `cancel` — Cancel appointment
- `appointment_lookup` — Find existing appointments
- `customer_lookup` — Find customer records
- `service_lookup` — Service information
- `business_info` — Business hours, location, contact
- `faq` — Frequently asked questions
- `human_handoff` — Escalate to human
- `emergency` — Medical emergency detection
- `general_conversation` — Greetings, small talk

## Tool Execution

All business operations go through registered tools. The LLM never directly accesses the database.

## Agent Events

Every node transition and tool call is recorded in the `agent_events` table for observability.
