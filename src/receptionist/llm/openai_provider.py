from typing import Any

from pydantic import BaseModel

from receptionist.config import get_settings
from receptionist.llm.base import BaseLLMProvider

_settings = get_settings()


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=_settings.openai_api_key)
        self.model = _settings.openai_model

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def structured_complete(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> BaseModel:
        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=schema,
            temperature=temperature,
        )
        return schema.model_validate_json(response.choices[0].message.content or "{}")
