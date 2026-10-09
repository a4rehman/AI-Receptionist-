from receptionist.llm.base import BaseLLMProvider
from receptionist.llm.classifier import ClassificationResult, RuleBasedIntentClassifier
from receptionist.llm.intent import IntentClassifier
from receptionist.llm.mock_provider import MockLLMProvider


def get_llm_provider() -> BaseLLMProvider:
    from receptionist.config import get_settings
    settings = get_settings()
    if settings.llm_provider == "openai":
        from receptionist.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif settings.llm_provider == "anthropic":
        from receptionist.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    return MockLLMProvider()


__all__ = [
    "BaseLLMProvider",
    "ClassificationResult",
    "IntentClassifier",
    "MockLLMProvider",
    "RuleBasedIntentClassifier",
    "get_llm_provider",
]
