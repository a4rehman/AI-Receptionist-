# Tools Documentation

## Tool Registry

All tools are registered with:
- `name` — Unique tool name
- `description` — LLM-readable description
- `input_schema` — Pydantic validation schema
- `permission` — `read` or `write`

## Customer Tools
- `get_customer` — Get customer by ID
- `find_customer_by_phone` — Find by phone
- `find_customer_by_email` — Find by email
- `create_customer` — Create new customer
- `update_customer` — Update customer info
- `get_customer_appointments` — Get customer appointments

## Staff Tools
- `list_staff` — List all staff
- `get_staff` — Get staff by ID
- `search_staff` — Search staff
- `get_staff_services` — Get staff services
- `get_staff_schedule` — Get staff schedule

## Service Tools
- `list_services` — List all services
- `get_service` — Get service by ID
- `search_services` — Search services
- `get_service_price` — Get service price
- `get_service_duration` — Get service duration
- `get_service_staff` — Get staff for service

## Availability Tools
- `get_availability` — Get available slots

## Booking Tools
- `create_booking` — Create appointment
- `cancel_booking` — Cancel appointment
- `reschedule_booking` — Reschedule appointment

## Business Tools
- `get_business_info` — Get business info
- `get_business_hours` — Get operating hours
- `get_locations` — Get locations

## FAQ Tools
- `search_faq` — Search FAQ knowledge base

## Human Handoff Tools
- `create_handoff` — Create human handoff
