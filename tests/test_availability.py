from datetime import date, datetime, time, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from receptionist.db.models import (
    Appointment,
    AppointmentStatus,
    Base,
    BusinessHours,
    Customer,
    Service,
    Staff,
    StaffSchedule,
    StaffService,
    Tenant,
)
from receptionist.services.availability import AvailabilityService


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
async def test_get_available_slots(db_session, sample_data):
    service = AvailabilityService(db_session)
    target_date = date.today() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    slots = await service.get_available_slots(
        tenant_id=sample_data["tenant_id"],
        service_id=sample_data["service_id"],
        target_date=target_date,
    )
    assert len(slots) > 0
    assert all("start_time" in s for s in slots)


@pytest.mark.asyncio
async def test_booked_slot_not_available(db_session, sample_data):
    target_date = date.today() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    booked_start = datetime.combine(target_date, time(10, 0))
    booked_end = datetime.combine(target_date, time(10, 30))
    apt = Appointment(
        id="apt1", tenant_id=sample_data["tenant_id"],
        customer_id=sample_data["customer_id"],
        staff_id=sample_data["staff_id"],
        service_id=sample_data["service_id"],
        start_time=booked_start, end_time=booked_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(apt)
    await db_session.commit()

    service = AvailabilityService(db_session)
    slots = await service.get_available_slots(
        tenant_id=sample_data["tenant_id"],
        service_id=sample_data["service_id"],
        target_date=target_date,
    )
    for slot in slots:
        assert slot["start_time"] != "10:00"
