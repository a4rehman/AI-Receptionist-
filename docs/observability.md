# Observability Documentation

## Structured Logging

All logs are JSON-formatted with:
- `timestamp` — ISO 8601
- `level` — Log level
- `trace_id` — Request trace ID
- `tenant_id` — Tenant identifier
- `run_id` — Agent run ID
- `node` — Current graph node
- `tool` — Tool name (if applicable)
- `duration_ms` — Execution time

## Agent Events

Stored in `agent_events` table:
- `RUN_STARTED` — Agent run begins
- `NODE_STARTED` — Graph node starts
- `NODE_COMPLETED` — Graph node completes
- `TOOL_STARTED` — Tool execution starts
- `TOOL_COMPLETED` — Tool execution completes
- `TOOL_FAILED` — Tool execution fails
- `WAITING_FOR_USER` — Agent waiting for user input
- `BOOKING_CREATED` — Appointment booked
- `BOOKING_UPDATED` — Appointment rescheduled
- `BOOKING_CANCELLED` — Appointment cancelled
- `HANDOFF_CREATED` — Human handoff created
- `RUN_COMPLETED` — Agent run completes
- `RUN_FAILED` — Agent run fails

## LangSmith Compatibility

Trace structure compatible with LangSmith format. Can export via callback handler.

## Dashboard

The Streamlit dashboard shows:
- Live agent runs with current node
- Tool execution status
- Duration metrics
- Error tracking
