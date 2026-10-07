# Multi-Tenancy Documentation

## Tenant Model

Each business is a tenant with:
- Unique `tenant_id`
- Business type (hospital, dental, salon, restaurant, etc.)
- Configuration (timezone, currency, business hours)
- Services, staff, locations
- Booking rules and policies
- AI personality and system instructions
- Enabled tools

## Tenant Isolation

### Database Level
- Every tenant-scoped table has `tenant_id` column
- Repository layer injects `tenant_id` into every query
- No cross-tenant queries possible

### Application Level
- Tenant context set at API boundary
- Context flows through agent state to tools
- Context cleared after request

### Testing
- `test_tenant_isolation.py` verifies:
  - Tenant A cannot list Tenant B customers
  - Tenant A cannot get Tenant B customer by ID
  - Tenant A cannot delete Tenant B customer

## Tenant Configuration

```json
{
  "tenant_id": "clinic_001",
  "business_type": "dental_clinic",
  "business_name": "ABC Dental",
  "timezone": "America/New_York",
  "currency": "USD",
  "booking_enabled": true,
  "cancellation_policy": {"min_hours_notice": 24},
  "notification_settings": {"email": true, "sms": false},
  "ai_personality": "professional_friendly",
  "enabled_tools": ["get_services", "get_availability", "create_booking"]
}
```
