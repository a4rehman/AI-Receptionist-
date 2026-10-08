from typing import Any, Optional

import pytest

from receptionist.llm.base import BaseLLMProvider
from receptionist.llm.classifier import ClassificationResult, RuleBasedIntentClassifier
from receptionist.llm.intent import ALLOWED_INTENTS, IntentClassifier


class TestIntentClassifier:
    def setup_method(self):
        self.classifier = RuleBasedIntentClassifier()

    def test_booking_intent(self):
        result = self.classifier.classify("I want to book an appointment")
        assert result.intent == "booking"
        assert result.confidence > 0.5

    def test_cancel_intent(self):
        result = self.classifier.classify("Cancel my appointment")
        assert result.intent == "cancel"

    def test_reschedule_intent(self):
        result = self.classifier.classify("Move my appointment to Friday")
        assert result.intent == "reschedule"

    def test_emergency_intent(self):
        result = self.classifier.classify("I am having severe chest pain")
        assert result.intent == "emergency"

    def test_human_handoff_intent(self):
        result = self.classifier.classify("I want to speak to a human")
        assert result.intent == "human_handoff"

    def test_availability_intent(self):
        result = self.classifier.classify("What times are available tomorrow?")
        assert result.intent == "availability"

    def test_appointment_lookup_intent(self):
        result = self.classifier.classify("What appointments do I have?")
        assert result.intent == "appointment_lookup"

    def test_service_lookup_intent(self):
        result = self.classifier.classify("What services do you offer?")
        assert result.intent == "service_lookup"

    def test_business_info_intent(self):
        result = self.classifier.classify("What are your hours?")
        assert result.intent == "business_info"

    def test_faq_intent(self):
        result = self.classifier.classify("Do you accept insurance?")
        assert result.intent == "faq"

    def test_general_conversation(self):
        result = self.classifier.classify("Hello")
        assert result.intent == "general_conversation"

    def test_entity_extraction_date(self):
        result = self.classifier.classify("I want to book tomorrow")
        assert "date" in result.entities

    def test_entity_extraction_time(self):
        result = self.classifier.classify("I want to book at 3pm")
        assert "time" in result.entities


BOOKING_MSG = "I'd like to book a dental cleaning tomorrow at 10:00 am"


class StubProvider(BaseLLMProvider):
    def __init__(self, result: Optional[ClassificationResult] = None, error: Optional[Exception] = None):
        self.result = result
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages, temperature=0.7, max_tokens=1024, **kwargs: Any) -> str:
        return "stub"

    async def structured_complete(self, messages, schema, temperature=0.3, **kwargs: Any) -> Any:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.result


def test_allowed_intents_match_rule_engine():
    rules = RuleBasedIntentClassifier()
    result = rules.classify(BOOKING_MSG)
    assert result.intent == "booking"
    assert result.intent in ALLOWED_INTENTS


def test_no_provider_falls_back_to_rules(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    from receptionist.config import get_settings

    get_settings.cache_clear()
    try:
        classifier = IntentClassifier()
        assert classifier.provider is None
        result = classifier.classify(BOOKING_MSG)
        assert result.intent == "booking"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mock_provider_classification_matches_rules(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    from receptionist.config import get_settings

    get_settings.cache_clear()
    try:
        classifier = IntentClassifier()
        result = await classifier.aclassify(BOOKING_MSG)
        assert result.intent == "booking"
        assert "date" in result.entities
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_llm_overrides_intent_and_merges_entities():
    provider = StubProvider(
        ClassificationResult(intent="cancel", confidence=0.9, entities={"appointment_id": "apt_123"})
    )
    classifier = IntentClassifier(provider=provider)

    result = await classifier.aclassify(BOOKING_MSG)

    assert result.intent == "cancel"
    assert result.confidence == pytest.approx(0.9)
    # rule-derived entities survive the merge
    assert "date" in result.entities
    # LLM-supplied entities are kept
    assert result.entities["appointment_id"] == "apt_123"
    assert provider.calls and provider.calls[0][0]["role"] == "system"


@pytest.mark.asyncio
async def test_rule_entities_win_on_conflict():
    provider = StubProvider(
        ClassificationResult(intent="booking", confidence=0.9, entities={"date": "1999-01-01"})
    )
    classifier = IntentClassifier(provider=provider)

    result = await classifier.aclassify(BOOKING_MSG)

    rules_date = RuleBasedIntentClassifier().classify(BOOKING_MSG).entities["date"]
    assert result.entities["date"] == rules_date


@pytest.mark.asyncio
async def test_invalid_llm_intent_falls_back():
    provider = StubProvider(ClassificationResult(intent="totally_made_up", confidence=0.99))
    result = await IntentClassifier(provider=provider).aclassify(BOOKING_MSG)
    assert result.intent == "booking"


@pytest.mark.asyncio
async def test_llm_error_falls_back():
    provider = StubProvider(error=RuntimeError("boom"))
    result = await IntentClassifier(provider=provider).aclassify(BOOKING_MSG)
    assert result.intent == "booking"


@pytest.mark.asyncio
async def test_recent_history_is_included():
    provider = StubProvider(ClassificationResult(intent="booking", confidence=0.9))

    class Msg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    history = [Msg("user", "hello"), Msg("assistant", "hi"), Msg("user", "I need an appointment")]
    await IntentClassifier(provider=provider).aclassify(BOOKING_MSG, history)

    sent = provider.calls[0]
    assert sent[-1] == {"role": "user", "content": BOOKING_MSG}
    assert {"role": "user", "content": "I need an appointment"} in sent
