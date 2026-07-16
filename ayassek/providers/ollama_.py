from __future__ import annotations

import json
import uuid
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


class OllamaProvider(BaseProvider):
    provider_id = "ollama"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url or "http://localhost:11434", api_key)
        self._logger = get_logger("ollama_provider")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            content = msg.content
            images: list[str] = []
            text_parts = []
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            b64 = url.split(",", 1)[-1] if "," in url else url
                            images.append(b64)
                        elif url:
                            images.append(url)
            if isinstance(content, str):
                text_parts = [content]
            msg_dict: dict[str, Any] = {"role": msg.role, "content": "\n".join(text_parts)}
            if images:
                msg_dict["images"] = images
            result.append(msg_dict)
        return result

    async def list_models(self) -> list[ModelInfo]:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                models.append(ModelInfo(
                    id=name,
                    name=name,
                    provider=self.provider_id,
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision="llava" in name.lower() or "vision" in name.lower() or "-vl" in name.lower() or ":vl" in name.lower(),
                ))
            return models
        except Exception as e:
            self._logger.warning("Failed to list Ollama models: %s", e)
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
            "messages": await self._convert_messages(messages),
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
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._logger.error("Ollama API error: %s", e)
            raise
        except httpx.RequestError as e:
            self._logger.error("Ollama request failed: %s", e)
            raise
        data = resp.json()
        msg = data.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")
        formatted_tool_calls = None
        if tool_calls:
            formatted_tool_calls = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", {})
                if isinstance(raw_args, dict):
                    raw_args = json.dumps(raw_args)
                formatted_tool_calls.append({
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": raw_args,
                    },
                })
        return ChatResponse(
            message=ChatMessage(role="assistant", content=content, tool_calls=formatted_tool_calls),
            usage={"prompt_tokens": data.get("prompt_eval_count", 0), "completion_tokens": data.get("eval_count", 0)},
            model=data.get("model", payload.get("model", "")),
        )

    async def _stream_chat(self, payload: dict[str, Any]):
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    done = data.get("done", False)
                    if "message" in data:
                        token = data["message"].get("content", "")
                        tool_calls = data["message"].get("tool_calls")
                        formatted_tool_calls = None
                        if tool_calls:
                            formatted_tool_calls = []
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                raw_args = fn.get("arguments", {})
                                if isinstance(raw_args, dict):
                                    raw_args = json.dumps(raw_args)
                                formatted_tool_calls.append({
                                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                                    "type": "function",
                                    "function": {
                                        "name": fn.get("name", ""),
                                        "arguments": raw_args,
                                    },
                                })
                        yield ChatChunk(
                            token=token,
                            finish_reason="stop" if done else None,
                            tool_calls=formatted_tool_calls,
                        )
                    if done:
                        return
        except httpx.HTTPStatusError as e:
            self._logger.error("Ollama streaming error: %s", e)
            raise
        except httpx.RequestError as e:
            self._logger.error("Ollama streaming request failed: %s", e)
            raise

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()

    def supports_streaming(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return True