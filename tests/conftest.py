import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from receptionist.db.models import Base


@pytest_asyncio.fixture(autouse=True)
async def _patched_session_factory(tmp_path, monkeypatch):
    """Give every test its own SQLite file and point the app's session factory at it.

    The agent graph opens DB sessions from receptionist.db.engine at call time,
    so patching that module makes the real production path run against the
    test database instead of TiDB.
    """
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import sys
    monkeypatch.setattr(sys.modules["receptionist.db.engine"], "async_session_factory", session_factory)

    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_patched_session_factory):
    async with _patched_session_factory() as session:
        yield session


@pytest.fixture
def sample_tenant_id():
    return "test_tenant_001"


@pytest.fixture
def sample_customer_data():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
    }
