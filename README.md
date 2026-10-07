# 100Solutionz AI Receptionist

Universal AI Receptionist Platform for multi-business deployment.

## Features

- **Multi-tenant architecture** — Each business is a tenant with isolated data
- **LangGraph agent** — Tool-using AI receptionist with intent classification
- **Business tools** — Booking, cancellation, rescheduling, customer management, availability
- **Multi-business support** — Hospital, dental, salon, restaurant, hotel, and more
- **FastAPI backend** — RESTful API with tenant-aware endpoints
- **Streamlit dashboard** — Admin panel with live agent monitoring
- **Notification system** — Email, SMS, WhatsApp provider abstraction
- **Idempotency** — Safe retries for booking operations
- **Audit logging** — Complete audit trail for all operations

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start API
uvicorn receptionist.main:app --reload

# Start Dashboard (new terminal)
streamlit run src/receptionist/dashboard/app.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message to AI receptionist |
| GET | `/api/v1/appointments` | List appointments |
| GET | `/api/v1/appointments/{id}` | Get appointment details |
| GET | `/api/v1/availability` | Check available slots |
| GET | `/api/v1/services` | List services |
| GET | `/api/v1/staff` | List staff |
| GET | `/api/v1/customers` | List customers |
| POST | `/api/v1/handoff` | Create human handoff |
| GET | `/api/v1/agent-runs` | List agent runs |
| GET | `/api/v1/agent-events` | List agent events |

## Architecture

See `docs/ARCHITECTURE.md` for detailed architecture documentation.

## Testing

```bash
pytest tests/ -v
```

## Development

Set `APP_ENV=development` and `DRY_RUN=true` in `.env` to disable real notifications.

## License

Proprietary — 100Solutionz
