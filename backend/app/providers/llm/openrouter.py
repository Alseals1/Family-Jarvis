import json
import httpx

from app.providers.llm.base import LLMProvider, Message
from app.config import get_settings


class OpenRouterProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.openrouter_base_url
        self._api_key = settings.openrouter_api_key

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://family-jarvis.app",
            "X-Title": "Family JARVIS",
        }

    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "temperature": temperature,
                },
            )
            if response.status_code == 429:
                raise httpx.HTTPStatusError(
                    "JARVIS is thinking too fast — please wait a moment and try again.",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def complete_structured(
        self,
        messages: list[Message],
        schema: dict,
        model: str,
    ) -> dict:
        schema_instruction = Message(
            role="system",
            content=(
                "You must respond with valid JSON only, no markdown, no explanation. "
                f"The JSON must match this schema: {json.dumps(schema)}"
            ),
        )
        text = await self.complete([schema_instruction] + messages, model, temperature=0.0)
        # Strip markdown code fences if the model wraps the JSON
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())


def get_llm_provider() -> LLMProvider:
    return OpenRouterProvider()
