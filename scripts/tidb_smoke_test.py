"""
TiDB Cloud Smoke Test Script

Tests the complete booking lifecycle against a real TiDB database.
Uses a dedicated test tenant — NEVER uses real customer data.

Usage:
    python scripts/tidb_smoke_test.py

Required environment variables:
    TIDB_HOST, TIDB_PORT, TIDB_USER, TIDB_PASSWORD, TIDB_DATABASE
"""

import asyncio
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from receptionist.config import get_settings
from receptionist.db.models import (
    Base, Tenant, Location, Staff, Service, StaffService,
    StaffSchedule, BusinessHours, Customer, Appointment,
    AppointmentStatus, Conversation, Message, AgentRun,
    HumanHandoff, AuditLog, IdempotencyKey,
)
from receptionist.db.tenant import set_current_tenant, clear_current_tenant
from receptionist.services.availability import AvailabilityService
from receptionist.tools.booking_tools import create_booking, CreateBookingArgs, ToolContext
from receptionist.tools.cancellation_tools import cancel_booking, CancelBookingArgs
from receptionist.tools.reschedule_tools import reschedule_booking, RescheduleBookingArgs

TEST_TENANT_ID = "production_smoke_test_tenant"


async def run_smoke_test():
    settings = get_settings()

    if not settings.tidb_host:
        print("ERROR: TIDB_HOST not set. This script requires a real TiDB connection.")
        return False

    database_url = (
        f"mysql+aiomysql://{settings.tidb_user}:{settings.tidb_password}"
        f"@{settings.tidb_host}:{settings.tidb_port}/{settings.tidb_database}"
    )

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 60)
    print("TIDB CLOUD SMOKE TEST")
    print("=" * 60)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[PASS] Database tables created/verified")

        async with session_factory() as session:
            tenant = Tenant(
                id=TEST_TENANT_ID,
                business_type="dental_clinic",
                business_name="Smoke Test Clinic",
                timezone="UTC",
            )
            session.add(tenant)
            await session.commit()
            print(f"[PASS] Test tenant created: {TEST_TENANT_ID}")

        set_current_tenant(TEST_TENANT_ID)
        async with session_factory() as session:
            location = Location(
                id="loc_test_001",
                tenant_id=TEST_TENANT_ID,
                name="Main Branch",
                address="123 Test Street",
            )
            session.add(location)

            staff = Staff(
                id="staff_test_001",
                tenant_id=TEST_TENANT_ID,
                name="Dr. Test Doctor",
                role="dentist",
                department="Dental",
            )
            session.add(staff)

            service = Service(
                id="svc_test_001",
                tenant_id=TEST_TENANT_ID,
                name="Test Cleaning",
                duration_minutes=30,
                price=100.0,
            )
            session.add(service)
            session.add(StaffService(staff_id="staff_test_001", service_id="svc_test_001"))

            for day in range(5):
                session.add(StaffSchedule(
                    staff_id="staff_test_001",
                    day_of_week=day,
                    start_time="09:00",
                    end_time="17:00",
                ))
                session.add(BusinessHours(
                    tenant_id=TEST_TENANT_ID,
                    day_of_week=day,
                    start_time="09:00",
                    end_time="17:00",
                ))

            customer = Customer(
                id="cust_test_001",
                tenant_id=TEST_TENANT_ID,
                first_name="Test",
                last_name="Customer",
                email="test@example.com",
            )
            session.add(customer)
            await session.commit()
            print("[PASS] Test data created (location, staff, service, customer)")

        async with session_factory() as session:
            availability = AvailabilityService(session)
            target_date = date.today() + timedelta(days=1)
            while target_date.weekday() >= 5:
                target_date += timedelta(days=1)

            slots = await availability.get_available_slots(
                tenant_id=TEST_TENANT_ID,
                service_id="svc_test_001",
                target_date=target_date,
            )
            if not slots:
                print("[FAIL] No available slots found")
                return False
            print(f"[PASS] Availability check: {len(slots)} slots available")

        async with session_factory() as session:
            ctx = ToolContext(
                tenant_id=TEST_TENANT_ID,
                conversation_id="conv_smoke_test",
                customer_id="cust_test_001",
                db_session=session,
            )
            target_date = date.today() + timedelta(days=1)
            while target_date.weekday() >= 5:
                target_date += timedelta(days=1)

            booking_args = CreateBookingArgs(
                customer_id="cust_test_001",
                service_id="svc_test_001",
                date=target_date.isoformat(),
                time="10:00",
                idempotency_key=f"smoke_test_{uuid.uuid4().hex[:8]}",
            )
            result = await create_booking(booking_args, ctx)
            if not result.success:
                print(f"[FAIL] Booking failed: {result.error}")
                return False
            appointment_id = result.data["appointment_id"]
            print(f"[PASS] Booking created: {appointment_id}")

        async with session_factory() as session:
            result = await session.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            apt = result.scalar_one_or_none()
            if not apt:
                print("[FAIL] Appointment not found in database")
                return False
            if apt.status != AppointmentStatus.CONFIRMED:
                print(f"[FAIL] Appointment status is {apt.status}, expected CONFIRMED")
                return False
            print("[PASS] Appointment verified in database")

        async with session_factory() as session:
            availability = AvailabilityService(session)
            target_date = date.today() + timedelta(days=1)
            while target_date.weekday() >= 5:
                target_date += timedelta(days=1)

            slots = await availability.get_available_slots(
                tenant_id=TEST_TENANT_ID,
                service_id="svc_test_001",
                target_date=target_date,
            )
            slot_times = [s["start_time"] for s in slots]
            if "10:00" in slot_times:
                print("[FAIL] Booked slot still shows as available")
                return False
            print("[PASS] Booked slot no longer available")

        async with session_factory() as session:
            ctx = ToolContext(
                tenant_id=TEST_TENANT_ID,
                conversation_id="conv_smoke_test",
                customer_id="cust_test_001",
                db_session=session,
            )
            new_date = date.today() + timedelta(days=2)
            while new_date.weekday() >= 5:
                new_date += timedelta(days=1)

            reschedule_args = RescheduleBookingArgs(
                appointment_id=appointment_id,
                customer_id="cust_test_001",
                new_date=new_date.isoformat(),
                new_time="11:00",
                idempotency_key=f"smoke_test_reschedule_{uuid.uuid4().hex[:8]}",
            )
            result = await reschedule_booking(reschedule_args, ctx)
            if not result.success:
                print(f"[FAIL] Reschedule failed: {result.error}")
                return False
            print(f"[PASS] Appointment rescheduled to {new_date} at 11:00")

        async with session_factory() as session:
            ctx = ToolContext(
                tenant_id=TEST_TENANT_ID,
                conversation_id="conv_smoke_test",
                customer_id="cust_test_001",
                db_session=session,
            )
            cancel_args = CancelBookingArgs(
                appointment_id=appointment_id,
                customer_id="cust_test_001",
                idempotency_key=f"smoke_test_cancel_{uuid.uuid4().hex[:8]}",
            )
            result = await cancel_booking(cancel_args, ctx)
            if not result.success:
                print(f"[FAIL] Cancellation failed: {result.error}")
                return False
            print("[PASS] Appointment cancelled")

        async with session_factory() as session:
            result = await session.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            apt = result.scalar_one_or_none()
            if not apt or apt.status != AppointmentStatus.CANCELLED:
                print("[FAIL] Appointment status not updated to CANCELLED")
                return False
            print("[PASS] Cancellation verified in database")

        async with session_factory() as session:
            result = await session.execute(
                select(Appointment).where(Appointment.tenant_id == TEST_TENANT_ID)
            )
            count = len(result.scalars().all())
            if count != 1:
                print(f"[FAIL] Expected 1 appointment, found {count}")
                return False
            print("[PASS] No duplicate appointments")

        clear_current_tenant()
        print("=" * 60)
        print("ALL SMOKE TESTS PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"[FAIL] Smoke test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(run_smoke_test())
    exit(0 if success else 1)
