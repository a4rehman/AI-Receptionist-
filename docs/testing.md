# Testing Documentation

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_datetime_utils.py   # Date/time parsing
├── test_intent_classifier.py # Intent classification
├── test_tenant_isolation.py # Multi-tenant security
├── test_availability.py     # Availability engine
├── test_booking.py          # Booking engine
└── e2e/                     # End-to-end tests
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_booking.py -v

# With coverage
pytest tests/ --cov=src/receptionist --cov-report=html
```

## Test Categories

### Unit Tests
- Intent classification
- Date/time parsing
- PII redaction
- Tool validation

### Integration Tests
- Database operations
- Availability engine
- Booking engine
- Tenant isolation

### E2E Tests
- Full conversation flows
- Booking scenarios
- Cancellation scenarios
- Emergency detection

## Concurrency Tests

Double-booking prevention tested with:
- Simultaneous booking requests
- Idempotent retry verification
- Database transaction isolation
