from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ayassek.providers.base import (
    BaseProvider,
    ChatChunk,
    ChatMessage,
    ChatResponse,
    ModelInfo,
)
from ayassek.utils.logging import get_logger


class OpenAIProvider(BaseProvider):
    provider_id = "openai"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url or "https://api.openai.com/v1", api_key)
        self._logger = get_logger("openai_provider")
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(
                f"{self.base_url}/models",
                headers=await self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                models.append(ModelInfo(
                    id=m["id"],
                    name=m["id"],
                    provider=self.provider_id,
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision="vision" in m["id"].lower() or "gpt-4o" in m["id"].lower(),
                ))
            return models
        except Exception as e:
            self._logger.warning("Failed to list OpenAI models: %s", e)
            return []

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk] | ChatResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    **(m.tool_calls and {"tool_calls": m.tool_calls} or {}),
                    **(m.tool_call_id and {"tool_call_id": m.tool_call_id} or {}),
                }
                for m in messages
            ],
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        payload.update(kwargs)

        if stream:
            return self._stream_chat(payload)
        else:
            return await self._non_stream_chat(payload)

    async def _non_stream_chat(self, payload: dict[str, Any]) -> ChatResponse:
        try:
            resp = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers=await self._headers(),
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._logger.error("OpenAI API error: %s", e)
            raise
        except httpx.RequestError as e:
            self._logger.error("OpenAI request failed: %s", e)
            raise
        data = resp.json()
        if not data.get("choices"):
            self._logger.error("OpenAI response missing choices: %s", data)
            raise RuntimeError("No choices in OpenAI response")
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls")
        return ChatResponse(
            message=ChatMessage(role="assistant", content=content, tool_calls=tool_calls),
            usage=data.get("usage"),
            model=data.get("model", payload.get("model", "")),
        )

    async def _stream_chat(self, payload: dict[str, Any]):
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=await self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        yield ChatChunk(finish_reason="stop")
                        return
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    token = delta.get("content", "") or ""
                    finish = choices[0].get("finish_reason")
                    tool_calls = delta.get("tool_calls")
                    yield ChatChunk(
                        token=token,
                        finish_reason=finish,
                        tool_calls=tool_calls,
                    )
                    if finish:
                        return
        except httpx.HTTPStatusError as e:
            self._logger.error("OpenAI streaming error: %s", e)
            raise
        except httpx.RequestError as e:
            self._logger.error("OpenAI streaming request failed: %s", e)
            raise

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(
                f"{self.base_url}/models",
                headers=await self._headers(),
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()

    def supports_streaming(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True