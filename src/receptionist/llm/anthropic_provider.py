from typing import Any
from pydantic import BaseModel
from receptionist.llm.base import BaseLLMProvider
from receptionist.config import get_settings

_settings = get_settings()


class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=_settings.anthropic_api_key)
        self.model = _settings.anthropic_model

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]

        response = await self.client.messages.create(
            model=self.model,
            system=system_msg,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text if response.content else ""

    async def structured_complete(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> BaseModel:
        import json
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]

        schema_json = json.dumps(schema.model_json_schema())
        response = await self.client.messages.create(
            model=self.model,
            system=f"{system_msg}\n\nRespond with JSON matching this schema: {schema_json}",
            messages=user_messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return schema.model_validate_json(response.content[0].text if response.content else "{}")
