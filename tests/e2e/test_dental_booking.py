import pytest
import pytest_asyncio
from datetime import date, timedelta
from receptionist.db.models import (
    Tenant, Staff, Service, StaffService, StaffSchedule,
    BusinessHours, Customer, Conversation,
)
from receptionist.agent.state import ReceptionistState
from receptionist.agent.graph import receptionist_graph
from receptionist.db.tenant import set_current_tenant, clear_current_tenant


@pytest_asyncio.fixture
async def dental_clinic(db_session):
    tenant = Tenant(id="dental_001", business_type="dental_clinic", business_name="ABC Dental", timezone="UTC")
    db_session.add(tenant)
    await db_session.flush()

    staff = Staff(id="dr_ahmed", tenant_id="dental_001", name="Dr Ahmed", role="dentist", department="Dental")
    db_session.add(staff)

    service = Service(id="cleaning", tenant_id="dental_001", name="Dental Cleaning", duration_minutes=30, price=80.0)
    db_session.add(service)
    db_session.add(StaffService(staff_id="dr_ahmed", service_id="cleaning"))

    for day in range(5):
        db_session.add(StaffSchedule(staff_id="dr_ahmed", day_of_week=day, start_time="09:00", end_time="17:00"))
        db_session.add(BusinessHours(tenant_id="dental_001", day_of_week=day, start_time="09:00", end_time="17:00"))

    customer = Customer(id="cust_001", tenant_id="dental_001", first_name="John", last_name="Doe", email="john@example.com")
    db_session.add(customer)

    await db_session.commit()
    return {"tenant_id": "dental_001", "customer_id": "cust_001", "service_id": "cleaning"}


@pytest.mark.asyncio
async def test_dental_booking_flow(db_session, dental_clinic):
    conv_id = "conv_dental_001"
    db_session.add(Conversation(id=conv_id, tenant_id=dental_clinic["tenant_id"], customer_id=dental_clinic["customer_id"]))
    await db_session.commit()

    set_current_tenant(dental_clinic["tenant_id"])
    try:
        state = ReceptionistState(
            tenant_id=dental_clinic["tenant_id"],
            conversation_id=conv_id,
            customer_id=dental_clinic["customer_id"],
            current_message="I want a cleaning tomorrow afternoon",
        )
        result = await receptionist_graph.ainvoke(
            state.model_dump(),
            config={"configurable": {"thread_id": conv_id}},
        )
        assert result["intent"] in ("booking", "availability")
        assert result["execution_status"] == "completed"
    finally:
        clear_current_tenant()
