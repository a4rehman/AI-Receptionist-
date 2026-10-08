import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from receptionist.db.models import Base, Tenant, Conversation
from receptionist.agent.state import ReceptionistState
from receptionist.agent.graph import receptionist_graph
from receptionist.db.tenant import set_current_tenant, clear_current_tenant


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_emergency_detection(db_session):
    tenant = Tenant(id="hospital_001", business_type="hospital", business_name="City Hospital")
    db_session.add(tenant)
    db_session.add(Conversation(id="conv_emergency", tenant_id="hospital_001"))
    await db_session.commit()

    set_current_tenant("hospital_001")
    try:
        state = ReceptionistState(
            tenant_id="hospital_001",
            conversation_id="conv_emergency",
            current_message="I am having severe chest pain",
        )
        result = await receptionist_graph.ainvoke(
            state.model_dump(),
            config={"configurable": {"thread_id": "conv_emergency"}},
        )
        assert result["emergency_detected"] is True
        assert result["human_handoff_required"] is True
        assert "emergency" in result["response"].lower() or "911" in result["response"]
    finally:
        clear_current_tenant()
