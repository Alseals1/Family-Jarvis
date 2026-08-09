from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
    ) -> str: ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[Message],
        schema: dict,
        model: str,
    ) -> dict: ...
