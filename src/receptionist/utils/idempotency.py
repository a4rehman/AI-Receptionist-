import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from receptionist.db.models import IdempotencyKey


def generate_idempotency_key() -> str:
    return str(uuid.uuid4())


async def check_idempotency(
    session: AsyncSession,
    tenant_id: str,
    operation: str,
    key: str,
) -> dict | None:
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.tenant_id == tenant_id,
        IdempotencyKey.operation == operation,
        IdempotencyKey.key == key,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        return record.result
    return None


async def save_idempotency_result(
    session: AsyncSession,
    tenant_id: str,
    operation: str,
    key: str,
    result: dict,
) -> None:
    record = IdempotencyKey(
        tenant_id=tenant_id,
        operation=operation,
        key=key,
        result=result,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
