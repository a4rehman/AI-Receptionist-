# Booking Engine Documentation

## Transactional Booking Flow

1. Validate tenant context
2. Validate customer exists
3. Validate service exists
4. Check availability (with `SELECT ... FOR UPDATE`)
5. Create appointment record
6. Create status history record
7. Write audit log
8. Queue confirmation notification
9. Return appointment ID

## Idempotency

- Client provides `idempotency_key` (UUID)
- Stored in `idempotency_keys` table
- Same key returns original result
- Prevents duplicate bookings on retry

## Double-Booking Prevention

- Availability re-checked inside transaction
- `SELECT ... FOR UPDATE` locks staff schedule
- Unique constraint on `idempotency_key`
- Concurrent requests serialized by database

## Cancellation Policy

- Configurable minimum notice period
- Policy checked before cancellation
- Audit log entry created
- Notification sent to customer

## Rescheduling

- Original appointment verified
- New slot availability checked
- Transactional update
- Status history tracked
- Notification sent
