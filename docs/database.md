# Database Documentation

## TiDB Cloud

The production database is TiDB Cloud (MySQL-compatible).

### Connection

Set these environment variables:
```
TIDB_HOST=gateway01.us-west-2.prod.aws.tidbcloud.com
TIDB_PORT=4000
TIDB_USER=root
TIDB_PASSWORD=your-password
TIDB_DATABASE=ai_receptionist
TIDB_SSL_MODE=verify-full
```

### Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Schema

### Core Tables
- `tenants` — Business tenants
- `tenant_settings` — Key-value configuration per tenant
- `customers` — Customer/patient records
- `staff` — Staff/doctor/stylist records
- `services` — Services offered
- `appointments` — Booked appointments
- `conversations` — Chat conversations
- `messages` — Individual messages
- `agent_runs` — Agent execution runs
- `agent_events` — Agent execution events
- `tool_calls` — Tool execution records
- `human_handoffs` — Human escalation records
- `notifications` — Notification records
- `audit_logs` — Audit trail
- `faqs` — FAQ knowledge base
- `idempotency_keys` — Idempotency tracking

## Tenant Isolation

Every tenant-scoped table has a `tenant_id` column. The repository layer enforces tenant filtering on every query.
