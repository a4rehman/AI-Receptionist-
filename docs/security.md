# Security Documentation

## Multi-Tenant Isolation

- Every query includes `tenant_id` filter
- Repository layer enforces tenant context
- Test: `test_tenant_isolation.py` verifies isolation

## Authentication

- API key header (`X-API-Key`) for API access
- JWT tokens for dashboard access (production)

## Authorization

- Role-based access control (RBAC)
- Tool permissions: `read` vs `write`
- Tenant admins can only access their tenant

## Data Protection

- PII redaction in logs
- Encrypted secrets in environment variables
- SSL/TLS for database connections
- Input validation via Pydantic schemas

## Prompt Injection Defense

- System prompt separation from user input
- Retrieved content marked as untrusted
- Tool descriptions include injection warnings
- Output filtering for sensitive patterns

## Medical Safety

- Emergency keyword detection triggers immediate escalation
- No diagnosis or medical advice
- Configurable emergency instructions per tenant
- Human handoff for medical concerns
