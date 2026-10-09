import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from receptionist.main import app

CLINIC_KEY = "test-api-key-123"       # bound to clinic_001 (tests/conftest.py)
OTHER_KEY = "other-key-456"           # bound to other_tenant
TEST_API_KEYS = "clinic_001:test-api-key-123,other_tenant:other-key-456"


@pytest.fixture
def client():
    return TestClient(app)


@pytest_asyncio.fixture(autouse=True)
async def seeded_tenants(db_session):
    from receptionist.db.models import Service, Tenant

    db_session.add(Tenant(id="clinic_001", business_type="dental_clinic",
                          business_name="Clinic A", timezone="UTC"))
    db_session.add(Tenant(id="other_tenant", business_type="dental_clinic",
                          business_name="Clinic B", timezone="UTC"))
    db_session.add(Service(id="svc_a", tenant_id="clinic_001", name="Clinic A Cleaning",
                           duration_minutes=30, price=50.0))
    db_session.add(Service(id="svc_b", tenant_id="other_tenant", name="Clinic B Root Canal",
                           duration_minutes=60, price=200.0))
    await db_session.commit()


def test_api_v1_requires_key(client):
    r = client.get("/api/v1/services")
    assert r.status_code == 401
    assert r.json()["detail"] == "API key required"


def test_invalid_key_rejected(client):
    r = client.get("/api/v1/services", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid API key"


def test_valid_key_scopes_tenant(client):
    r = client.get("/api/v1/services", headers={"X-API-Key": CLINIC_KEY})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert "Clinic A Cleaning" in names
    assert "Clinic B Root Canal" not in names


def test_header_tenant_mismatch_forbidden(client):
    r = client.get("/api/v1/services",
                   headers={"X-API-Key": CLINIC_KEY, "X-Tenant-ID": "other_tenant"})
    assert r.status_code == 403
    assert "does not match API key" in r.json()["detail"]


def test_chat_without_tenant_field_derives_from_key(client):
    r = client.post("/api/v1/chat", headers={"X-API-Key": CLINIC_KEY},
                    json={"message": "hello"})
    assert r.status_code == 200
    assert r.json()["conversation_id"].startswith("conv_")


def test_chat_tenant_mismatch_forbidden(client):
    r = client.post("/api/v1/chat", headers={"X-API-Key": CLINIC_KEY},
                    json={"tenant_id": "other_tenant", "message": "hello"})
    assert r.status_code == 403
    assert "does not match API key" in r.json()["detail"]


def test_chat_unknown_tenant_from_key_404(client, monkeypatch):
    monkeypatch.setenv("API_KEYS", "ghost_tenant:ghost-key-789")
    from receptionist.config import get_settings
    get_settings.cache_clear()
    try:
        r = client.post("/api/v1/chat", headers={"X-API-Key": "ghost-key-789"},
                        json={"message": "hello"})
        assert r.status_code == 404
        assert r.json()["detail"] == "Unknown tenant"
    finally:
        monkeypatch.setenv("API_KEYS", TEST_API_KEYS)
        get_settings.cache_clear()


def test_docs_and_health_open_without_key(client):
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200


def test_handoff_tenant_bound_to_key(client):
    r = client.post("/api/v1/handoff", headers={"X-API-Key": CLINIC_KEY},
                    json={"conversation_id": "conv_x", "reason": "test"})
    assert r.status_code == 200

    r = client.post("/api/v1/handoff", headers={"X-API-Key": CLINIC_KEY},
                    json={"tenant_id": "other_tenant", "conversation_id": "conv_x",
                          "reason": "test"})
    assert r.status_code == 403
