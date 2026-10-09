import pytest

from receptionist.agent.graph import receptionist_graph
from receptionist.agent.state import ReceptionistState
from receptionist.db.models import Conversation, Tenant
from receptionist.db.tenant import clear_current_tenant, set_current_tenant


@pytest.mark.asyncio
async def test_human_handoff_request(db_session):
    tenant = Tenant(id="clinic_001", business_type="medical_clinic", business_name="Health Clinic")
    db_session.add(tenant)
    db_session.add(Conversation(id="conv_handoff", tenant_id="clinic_001"))
    await db_session.commit()

    set_current_tenant("clinic_001")
    try:
        state = ReceptionistState(
            tenant_id="clinic_001",
            conversation_id="conv_handoff",
            current_message="I want to speak to a human",
        )
        result = await receptionist_graph.ainvoke(
            state.model_dump(),
            config={"configurable": {"thread_id": "conv_handoff"}},
        )
        assert result["intent"] == "human_handoff"
        assert result["human_handoff_required"] is True
    finally:
        clear_current_tenant()
