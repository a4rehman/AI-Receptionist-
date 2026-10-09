from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import structlog

from receptionist.llm.base import BaseLLMProvider
from receptionist.llm.classifier import (
    INTENT_PATTERNS,
    ClassificationResult,
    RuleBasedIntentClassifier,
)

logger = structlog.get_logger()

ALLOWED_INTENTS = set(INTENT_PATTERNS.keys())

SYSTEM_PROMPT = (
    "You classify a single customer message for an appointment-booking assistant. "
    "Respond only with the given schema. Choose exactly one intent from this list:\n"
    + "\n".join(f"- {intent}" for intent in sorted(ALLOWED_INTENTS))
    + "\nSet confidence between 0 and 1. Put any slots you can identify (date, time, "
    "service_name, staff_name) in entities, but do not invent values."
)


class IntentClassifier:
    """Intent classification with an optional LLM and a deterministic fallback.

    The rule engine is always used to extract entities (dates, times, service
    and staff names, appointment IDs) so the verified booking flow is unchanged.
    A configured LLM may only override the *intent* and add extra entities; the
    rule-based entities always win on key conflicts.
    """

    def __init__(self, provider: BaseLLMProvider | None = None):
        self._provider = provider
        self._rules = RuleBasedIntentClassifier()

    @property
    def provider(self) -> BaseLLMProvider | None:
        if self._provider is not None:
            return self._provider
        from receptionist.config import get_settings

        if get_settings().llm_provider == "mock":
            return None
        try:
            from receptionist.llm import get_llm_provider

            self._provider = get_llm_provider()
        except Exception as e:  # noqa: BLE001 - provider init must never break classification  # pragma: no cover - defensive
            logger.warning("llm_provider_init_failed", error=str(e))
        return self._provider

    def classify(self, message: str) -> ClassificationResult:
        """Deterministic, synchronous rule-based classification."""
        return self._rules.classify(message)

    async def aclassify(
        self,
        message: str,
        history: Iterable[Any] = (),
    ) -> ClassificationResult:
        rule_result = self._rules.classify(message)
        provider = self.provider
        if provider is None:
            return rule_result

        try:
            result = await provider.structured_complete(
                self._build_messages(message, history),
                ClassificationResult,
                temperature=0.0,
            )
        except Exception as e:  # noqa: BLE001 - fall back to rules on any provider error
            logger.warning("llm_intent_failed", error=str(e), tenant_free=True)
            return rule_result

        intent = getattr(result, "intent", None)
        if intent not in ALLOWED_INTENTS:
            logger.warning("llm_intent_invalid", intent=intent)
            return rule_result

        merged = dict(getattr(result, "entities", None) or {})
        merged.update(rule_result.entities)

        llm_confidence = float(getattr(result, "confidence", 0.0) or 0.0)
        confidence = max(rule_result.confidence, llm_confidence) if intent == rule_result.intent else llm_confidence

        logger.info(
            "intent_classified_llm",
            intent=intent,
            rule_intent=rule_result.intent,
            confidence=confidence,
        )
        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            entities=merged,
        )

    @staticmethod
    def _build_messages(
        message: str,
        history: Iterable[Any],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        recent = [
            m
            for m in history
            if getattr(m, "role", None) in ("user", "assistant") and getattr(m, "content", "")
        ][-4:]
        for m in recent:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": message})
        return messages
