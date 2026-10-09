from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from receptionist.db.models import (
    Base,
    BusinessHours,
    Customer,
    Service,
    Staff,
    StaffSchedule,
    StaffService,
    Tenant,
)
from receptionist.tools.booking_tools import CreateBookingArgs, ToolContext, create_booking


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_data(db_session):
    tenant = Tenant(id="t1", business_type="dental_clinic", business_name="Test Clinic")
    db_session.add(tenant)
    await db_session.flush()

    staff = Staff(id="s1", tenant_id="t1", name="Dr. Ahmed", role="dentist")
    db_session.add(staff)

    service = Service(id="svc1", tenant_id="t1", name="Cleaning", duration_minutes=30)
    db_session.add(service)

    db_session.add(StaffService(staff_id="s1", service_id="svc1"))

    for day in range(5):
        db_session.add(StaffSchedule(staff_id="s1", day_of_week=day, start_time="09:00", end_time="17:00"))
        db_session.add(BusinessHours(tenant_id="t1", day_of_week=day, start_time="09:00", end_time="17:00"))

    customer = Customer(id="c1", tenant_id="t1", first_name="John", last_name="Doe")
    db_session.add(customer)

    await db_session.commit()
    return {"tenant_id": "t1", "staff_id": "s1", "service_id": "svc1", "customer_id": "c1"}


@pytest.mark.asyncio
async def test_create_booking_success(db_session, sample_data):
    target_date = date.today() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    ctx = ToolContext(tenant_id=sample_data["tenant_id"], conversation_id="conv1", customer_id=sample_data["customer_id"], db_session=db_session)
    args = CreateBookingArgs(
        customer_id=sample_data["customer_id"],
        service_id=sample_data["service_id"],
        date=target_date.isoformat(),
        time="10:00",
    )
    result = await create_booking(args, ctx)
    assert result.success is True
    assert result.data["status"] == "confirmed"
    assert "appointment_id" in result.data


@pytest.mark.asyncio
async def test_create_booking_unavailable_slot(db_session, sample_data):
    target_date = date.today() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    ctx = ToolContext(tenant_id=sample_data["tenant_id"], conversation_id="conv1", customer_id=sample_data["customer_id"], db_session=db_session)
    args = CreateBookingArgs(
        customer_id=sample_data["customer_id"],
        service_id=sample_data["service_id"],
        date=target_date.isoformat(),
        time="25:00",
    )
    result = await create_booking(args, ctx)
    assert result.success is False


@pytest.mark.asyncio
async def test_idempotent_booking(db_session, sample_data):
    target_date = date.today() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    ctx = ToolContext(tenant_id=sample_data["tenant_id"], conversation_id="conv1", customer_id=sample_data["customer_id"], db_session=db_session)
    args = CreateBookingArgs(
        customer_id=sample_data["customer_id"],
        service_id=sample_data["service_id"],
        date=target_date.isoformat(),
        time="10:00",
        idempotency_key="test-idem-key-123",
    )
    result1 = await create_booking(args, ctx)
    assert result1.success is True

    result2 = await create_booking(args, ctx)
    assert result2.success is True
    assert result1.data["appointment_id"] == result2.data["appointment_id"]
