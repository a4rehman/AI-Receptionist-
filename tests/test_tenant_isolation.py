import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from receptionist.db.models import Base, Customer, Tenant
from receptionist.db.repository import TenantRepository
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
async def test_tenant_a_cannot_access_tenant_b_customers(db_session):
    tenant_a = Tenant(id="tenant_a", business_type="dental_clinic", business_name="Clinic A")
    tenant_b = Tenant(id="tenant_b", business_type="dental_clinic", business_name="Clinic B")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    customer_a = Customer(id="cust_a1", tenant_id="tenant_a", first_name="Alice", last_name="Smith")
    customer_b = Customer(id="cust_b1", tenant_id="tenant_b", first_name="Bob", last_name="Jones")
    db_session.add_all([customer_a, customer_b])
    await db_session.flush()

    set_current_tenant("tenant_a")
    repo = TenantRepository(Customer, db_session)
    customers = await repo.list_all()
    assert len(customers) == 1
    assert customers[0].id == "cust_a1"

    set_current_tenant("tenant_b")
    repo = TenantRepository(Customer, db_session)
    customers = await repo.list_all()
    assert len(customers) == 1
    assert customers[0].id == "cust_b1"

    clear_current_tenant()


@pytest.mark.asyncio
async def test_tenant_a_cannot_get_tenant_b_customer_by_id(db_session):
    tenant_a = Tenant(id="tenant_a", business_type="dental_clinic", business_name="Clinic A")
    tenant_b = Tenant(id="tenant_b", business_type="dental_clinic", business_name="Clinic B")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    customer_b = Customer(id="cust_b1", tenant_id="tenant_b", first_name="Bob", last_name="Jones")
    db_session.add(customer_b)
    await db_session.flush()

    set_current_tenant("tenant_a")
    repo = TenantRepository(Customer, db_session)
    result = await repo.get_by_id("cust_b1")
    assert result is None

    clear_current_tenant()


@pytest.mark.asyncio
async def test_tenant_a_cannot_delete_tenant_b_customer(db_session):
    tenant_a = Tenant(id="tenant_a", business_type="dental_clinic", business_name="Clinic A")
    tenant_b = Tenant(id="tenant_b", business_type="dental_clinic", business_name="Clinic B")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    customer_b = Customer(id="cust_b1", tenant_id="tenant_b", first_name="Bob", last_name="Jones")
    db_session.add(customer_b)
    await db_session.flush()

    set_current_tenant("tenant_a")
    repo = TenantRepository(Customer, db_session)
    deleted = await repo.delete("cust_b1")
    assert deleted is False

    clear_current_tenant()
