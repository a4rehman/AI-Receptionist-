import pytest
import pytest_asyncio

from receptionist.db.models import FAQ
from receptionist.tools.faq_tools import SearchFAQArgs, search_faq
from receptionist.tools.registry import ToolContext


@pytest_asyncio.fixture
async def seeded_faqs(db_session, sample_tenant_id):
    rows = [
        FAQ(tenant_id=sample_tenant_id, category="insurance",
            question="Do you accept insurance?",
            answer="Yes, we accept most major dental insurance plans.", is_active=True),
        FAQ(tenant_id=sample_tenant_id, category="policy",
            question="What is your cancellation policy?",
            answer="Please give at least 24 hours notice to cancel an appointment.",
            is_active=True),
        FAQ(tenant_id=sample_tenant_id, category="hours",
            question="What are your opening hours?",
            answer="We are open Monday to Friday from 9:00 AM to 5:00 PM.", is_active=True),
        FAQ(tenant_id=sample_tenant_id, category="policy",
            question="Inactive question about insurance?",
            answer="Should never be returned.", is_active=False),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return rows


def _ctx(tenant_id, db_session, enabled_tools=None):
    return ToolContext(
        tenant_id=tenant_id,
        conversation_id="conv_test",
        db_session=db_session,
        enabled_tools=enabled_tools or [],
    )


@pytest.mark.asyncio
async def test_full_sentence_query_matches(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="Do you accept insurance?"),
        _ctx(sample_tenant_id, db_session),
    )
    assert result.success
    assert result.data
    assert result.data[0]["category"] == "insurance"


@pytest.mark.asyncio
async def test_noisy_conversational_query_matches(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="hi, quick one - do you guys take insurance plans here?"),
        _ctx(sample_tenant_id, db_session),
    )
    assert result.success
    assert result.data
    assert result.data[0]["category"] == "insurance"


@pytest.mark.asyncio
async def test_unrelated_query_returns_no_hits(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="zzzz qqqq nonexistent xyzzy"),
        _ctx(sample_tenant_id, db_session),
    )
    assert result.success
    assert result.data == []


@pytest.mark.asyncio
async def test_category_filter(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="opening hours", category="hours"),
        _ctx(sample_tenant_id, db_session),
    )
    assert result.success
    assert [row["category"] for row in result.data] == ["hours"]


@pytest.mark.asyncio
async def test_inactive_rows_excluded(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="inactive question"),
        _ctx(sample_tenant_id, db_session),
    )
    assert result.success
    assert result.data == []


@pytest.mark.asyncio
async def test_tenant_isolation(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="insurance"),
        _ctx("other_tenant_xyz", db_session),
    )
    assert result.success
    assert result.data == []


@pytest.mark.asyncio
async def test_disabled_tool_is_rejected(db_session, sample_tenant_id, seeded_faqs):
    result = await search_faq(
        SearchFAQArgs(query="insurance"),
        _ctx(sample_tenant_id, db_session, enabled_tools=["list_services"]),
    )
    assert result.success is False
    assert "not enabled" in result.error
