from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        pass

    @abstractmethod
    async def structured_complete(
        self,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> BaseModel:
        pass
