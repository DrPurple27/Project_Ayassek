from __future__ import annotations

from typing import Any

from ayassek.providers.base import BaseProvider
from ayassek.providers.openai_ import OpenAIProvider
from ayassek.providers.ollama_ import OllamaProvider
from ayassek.providers.nim import NIMProvider
from ayassek.providers.vllm_ import VLLMProvider

_provider_map: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "nim": NIMProvider,
    "vllm": VLLMProvider,
}


def get_provider_class(provider_id: str) -> type[BaseProvider] | None:
    return _provider_map.get(provider_id)


def list_providers() -> list[dict[str, Any]]:
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "OpenAI API (GPT-4, GPT-4o, etc.)",
        },
        {
            "id": "ollama",
            "name": "Ollama",
            "description": "Local Ollama (Llama, Mistral, Qwen, etc.)",
        },
        {
            "id": "nim",
            "name": "NVIDIA NIM",
            "description": "NVIDIA NIM Inference Microservices",
        },
        {
            "id": "vllm",
            "name": "vLLM",
            "description": "Local vLLM server (OpenAI-compatible)",
        },
    ]


def create_provider(provider_id: str, base_url: str = "", api_key: str | None = None) -> BaseProvider | None:
    cls = get_provider_class(provider_id)
    if cls is None:
        return None
    return cls(base_url=base_url, api_key=api_key)