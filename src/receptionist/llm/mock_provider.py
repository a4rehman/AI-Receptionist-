from typing import Any

from pydantic import BaseModel

from receptionist.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[MOCK RESPONSE to: {last_user_msg[:100]}]"

    async def structured_complete(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> BaseModel:
        return schema()
