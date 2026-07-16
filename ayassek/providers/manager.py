from __future__ import annotations

from typing import Any

from ayassek.config.settings import settings
from ayassek.providers.base import BaseProvider, ModelInfo
from ayassek.providers.registry import create_provider, list_providers
from ayassek.utils.logging import get_logger


class ProviderManager:
    def __init__(self):
        self._logger = get_logger("provider_manager")
        self._providers: dict[str, BaseProvider] = {}
        self._models_cache: dict[str, list[ModelInfo]] = {}
        self._active_provider_id: str = settings.defaults.provider
        self._active_model: str = settings.defaults.model
        self._initialize()

    def _initialize(self):
        for pid in ["openai", "ollama", "nim", "vllm"]:
            cfg = settings.providers.get(pid)
            base_url = cfg.base_url if cfg else ""
            api_key = cfg.api_key if cfg else None

            if pid == "openai":
                api_key = settings.OPENAI_API_KEY or api_key
                base_url = settings.OPENAI_BASE_URL or base_url
            elif pid == "nim":
                api_key = settings.NIM_API_KEY or api_key
                base_url = settings.NIM_BASE_URL or base_url
            elif pid == "ollama":
                base_url = settings.OLLAMA_BASE_URL or base_url
            elif pid == "vllm":
                api_key = settings.VLLM_API_KEY or api_key
                base_url = settings.VLLM_BASE_URL or base_url

            provider = create_provider(pid, base_url=base_url, api_key=api_key)
            if provider:
                self._providers[pid] = provider

    async def auto_select_model(self) -> str:
        """Pick the best available model for the active provider, trying other providers if needed."""
        pid = self._active_provider_id
        models = self._models_cache.get(pid, [])
        model_ids = {m.id for m in models}

        preferred = [settings.defaults.model, settings.defaults.fallback_model]
        for m in preferred:
            if m in model_ids:
                self.set_active_model(m)
                self._logger.info("Auto-selected model: %s", m)
                return m

        if models:
            self.set_active_model(models[0].id)
            self._logger.info("Auto-selected first available model: %s", models[0].id)
            return models[0].id

        for other_pid, other_models in self._models_cache.items():
            if other_models:
                self.set_active_provider(other_pid)
                self.set_active_model(other_models[0].id)
                self._logger.info("Fell back to provider %s with model %s", other_pid, other_models[0].id)
                return other_models[0].id

        self._logger.warning("No models available from any provider, using default: %s", settings.defaults.model)
        return settings.defaults.model

    async def refresh_models(self, provider_id: str | None = None) -> dict[str, list[ModelInfo]]:
        pids = [provider_id] if provider_id else list(self._providers.keys())
        for pid in pids:
            provider = self._providers.get(pid)
            if provider:
                try:
                    models = await provider.list_models()
                    self._models_cache[pid] = models
                except Exception as e:
                    self._logger.warning("Failed to refresh models for %s: %s", pid, e)
                    self._models_cache[pid] = []
        return self._models_cache

    def get_provider(self, provider_id: str | None = None) -> BaseProvider | None:
        pid = provider_id or self._active_provider_id
        return self._providers.get(pid)

    def get_active_provider(self) -> BaseProvider | None:
        return self._providers.get(self._active_provider_id)

    def set_active_provider(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            self._active_provider_id = provider_id
            return True
        return False

    def set_active_model(self, model: str):
        self._active_model = model

    def get_active_model(self) -> str:
        return self._active_model

    def get_models(self, provider_id: str | None = None) -> list[ModelInfo]:
        pid = provider_id or self._active_provider_id
        return self._models_cache.get(pid, [])

    def get_provider_info(self) -> list[dict[str, Any]]:
        return list_providers()

    def get_status(self) -> dict[str, Any]:
        status = {}
        for pid, provider in self._providers.items():
            models = self._models_cache.get(pid, [])
            connected = len(models) > 0
            provider_info = {
                "connected": connected,
                "model_count": len(models),
                "base_url": provider.base_url,
                "streaming": provider.supports_streaming(),
                "tools": provider.supports_tools(),
                "vision": provider.supports_vision(),
            }
            if not connected:
                try:
                    import httpx
                    with httpx.Client(timeout=2.0) as client:
                        client.get(f"{provider.base_url}/health")
                except Exception as e:
                    provider_info["error"] = str(e)
            status[pid] = provider_info
        return status

    async def health_check(self, provider_id: str) -> bool:
        provider = self._providers.get(provider_id)
        if not provider:
            return False
        try:
            return await provider.health_check()
        except Exception:
            return False

    async def close_all(self):
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception as e:
                self._logger.warning("Error closing provider %s: %s", provider.provider_id, e)