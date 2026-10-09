"""
Database Seed Script

Creates default tenant, staff, services, schedules, and customer data.
Run this after migrations to populate the database with test data.

Usage:
    python scripts/seed_database.py
"""

import asyncio
import ssl
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from receptionist.config import get_settings
from receptionist.db.models import (
    FAQ,
    Base,
    BusinessHours,
    Customer,
    Location,
    Service,
    Staff,
    StaffSchedule,
    StaffService,
    Tenant,
    TenantSetting,
)

TEST_TENANT_ID = "clinic_001"

FAQ_SEED = [
    ("insurance", "Do you accept insurance?",
     ("Yes, we accept most major dental insurance plans. Please bring your insurance card "
      "to your first visit and we will verify your coverage before treatment.")),
    ("billing", "What payment methods do you accept?",
     ("We accept cash, credit and debit cards, and dental financing plans. Payment is due "
      "at the time of service.")),
    ("policy", "What is your cancellation policy?",
     ("Please give us at least 24 hours notice to cancel or reschedule an appointment. "
      "Late cancellations may incur a fee.")),
    ("hours", "What are your opening hours?",
     "We are open Monday to Friday from 9:00 AM to 5:00 PM."),
    ("visits", "What should I bring to my first appointment?",
     "Please bring a photo ID, your insurance card, and a list of any medications you take."),
    ("location", "Is parking available?",
     "Free parking is available in the lot next to our clinic at 123 Main St."),
]


async def seed_faqs(session: AsyncSession, tenant_id: str) -> int:
    """Idempotent FAQ backfill: only inserts when the tenant has none."""
    existing = (await session.execute(
        select(func.count()).select_from(FAQ).where(FAQ.tenant_id == tenant_id)
    )).scalar() or 0
    if existing:
        return 0
    for category, question, answer in FAQ_SEED:
        session.add(FAQ(
            tenant_id=tenant_id,
            category=category,
            question=question,
            answer=answer,
            is_active=True,
        ))
    await session.flush()
    return len(FAQ_SEED)


async def seed_database():
    settings = get_settings()

    database_url = settings.database_url_async
    if settings.tidb_host:
        database_url = (
            f"mysql+aiomysql://{settings.tidb_user}:{settings.tidb_password}"
            f"@{settings.tidb_host}:{settings.tidb_port}/{settings.tidb_database}"
        )

    ssl_context = ssl.create_default_context(cafile=settings.tidb_ca_path or None)
    if settings.tidb_ssl_mode == "preferred":
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "ssl": ssl_context,
            "connect_timeout": 10,
        },
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 60)
    print("DATABASE SEED SCRIPT")
    print("=" * 60)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[PASS] Tables created/verified")

        async with session_factory() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == TEST_TENANT_ID)
            )
            if result.scalar_one_or_none():
                print(f"[SKIP] Tenant {TEST_TENANT_ID} already exists")
                added = await seed_faqs(session, TEST_TENANT_ID)
                await session.commit()
                if added:
                    print(f"[PASS] FAQ backfill: {added} rows added")
                else:
                    print("[SKIP] FAQs already present")
                await engine.dispose()
                return

        async with session_factory() as session:
            tenant = Tenant(
                id=TEST_TENANT_ID,
                business_type="dental_clinic",
                business_name="ABC Dental Clinic",
                timezone="UTC",
                currency="USD",
                country="US",
                phone="+1234567890",
                email="info@abcdental.com",
                is_active=True,
            )
            session.add(tenant)
            await session.flush()

            settings_data = [
                ("timezone", "UTC"),
                ("min_cancellation_hours", "24"),
                ("max_booking_horizon_days", "90"),
                ("buffer_minutes", "0"),
                ("enabled_tools", "list_services,get_availability,create_booking,cancel_booking,reschedule_booking,get_customer,get_customer_appointments,get_staff,list_staff,get_business_info,search_faq"),
            ]
            for key, value in settings_data:
                session.add(TenantSetting(tenant_id=TEST_TENANT_ID, key=key, value=value))

            location = Location(
                id="loc_001",
                tenant_id=TEST_TENANT_ID,
                name="Main Branch",
                address="123 Main St",
                phone="+1234567890",
                timezone="UTC",
                is_active=True,
            )
            session.add(location)

            staff_members = [
                ("dr_ahmed", "Dr. Ahmed", "dentist", "General Dentistry", "Dental"),
                ("dr_sarah", "Dr. Sarah", "dentist", "Orthodontics", "Dental"),
                ("dr_michael", "Dr. Michael", "cardiologist", "Cardiology", "Cardiology"),
            ]
            for staff_id, name, role, spec, dept in staff_members:
                session.add(Staff(
                    id=staff_id,
                    tenant_id=TEST_TENANT_ID,
                    name=name,
                    role=role,
                    specialization=spec,
                    department=dept,
                    email=f"{staff_id}@abcdental.com",
                    phone="+1234567891",
                    is_active=True,
                ))
            await session.flush()

            services = [
                ("cleaning", "Dental Cleaning", "Professional dental cleaning", 30, 80.0),
                ("checkup", "Dental Checkup", "Routine dental examination", 30, 50.0),
                ("filling", "Dental Filling", "Cavity filling treatment", 45, 150.0),
                ("root_canal", "Root Canal", "Root canal treatment", 60, 500.0),
                ("cardio_consult", "Cardiology Consultation", "Heart specialist consultation", 30, 200.0),
            ]
            for svc_id, name, desc, duration, price in services:
                session.add(Service(
                    id=svc_id,
                    tenant_id=TEST_TENANT_ID,
                    name=name,
                    description=desc,
                    duration_minutes=duration,
                    price=price,
                    currency="USD",
                    is_active=True,
                ))
            await session.flush()

            staff_services = [
                ("dr_ahmed", "cleaning"), ("dr_ahmed", "checkup"), ("dr_ahmed", "filling"),
                ("dr_sarah", "checkup"), ("dr_sarah", "root_canal"),
                ("dr_michael", "cardio_consult"),
            ]
            for staff_id, service_id in staff_services:
                session.add(StaffService(staff_id=staff_id, service_id=service_id))

            for day in range(5):
                for staff_id, _, _, _, _ in staff_members:
                    session.add(StaffSchedule(
                        staff_id=staff_id,
                        day_of_week=day,
                        start_time="09:00",
                        end_time="17:00",
                        is_active=True,
                    ))
                session.add(BusinessHours(
                    tenant_id=TEST_TENANT_ID,
                    day_of_week=day,
                    start_time="09:00",
                    end_time="17:00",
                    is_closed=False,
                ))

            session.add(Customer(
                id="cust_001",
                tenant_id=TEST_TENANT_ID,
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                phone="+1234567899",
            ))

            faq_count = await seed_faqs(session, TEST_TENANT_ID)

            await session.commit()
            print(f"[PASS] Tenant created: {TEST_TENANT_ID}")
            print("[PASS] Settings, location, staff, services, schedules, customer added")
            print(f"[PASS] FAQ entries added: {faq_count}")

        print("=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"Tenant ID: {TEST_TENANT_ID}")
        print("Dashboard me 'clinic_001' daal ke data dekh sakte hain")

    except Exception as e:  # noqa: BLE001 - script entrypoint reports and exits
        print(f"[FAIL] Seed failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_database())
