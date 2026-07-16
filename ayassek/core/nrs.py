from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ayassek.config.settings import settings
from ayassek.providers.base import ChatMessage
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

NRS_MODEL = getattr(settings.nrs, "model", "qwen2.5:1.5b")
NRS_TEMPERATURE = getattr(settings.nrs, "temperature", 0.3)
NRS_PROVIDER_ORDER = getattr(settings.nrs, "provider_order", ["ollama", "vllm", "openai", "nim"])

NRS_SYSTEM_PROMPT = """You are the Neural Reasoning System (NRS) orchestrator for Ayassek, a multimodal AI agent.

Your job: analyze the user's message and decide memory operations.

Rules:
- RECALL: Search memory when the user references past topics, asks follow-up questions, or explicitly requests recall. Use specific, focused search queries.
- REMEMBER: Store when the user explicitly says "remember", "save", "store", or shares critical facts/decisions. Do NOT remember general conversation, greetings, questions, small talk, or anything the user didn't explicitly ask to save.
- Default to "none" unless there is a clear signal. When in doubt, do nothing.

Output ONLY valid JSON. No markdown, no explanations, no extra text."""

NRS_USER_PROMPT = """Existing memory topics: {existing_titles}

Recent conversation:
{recent_context}

User message: {user_message}

Decide memory operations. If unsure, use "none". Output JSON only:
{{"action": "<recall|remember|both|none>", "recall": {{"query": "<search query>", "n_results": 5}} | null, "remember": {{"title": "<short title>", "content": "<key facts to store>"}} | null}}"""

NRS_CONTRADICTION_PROMPT = """You are analyzing potential contradictions in a knowledge base.

Existing fact: "{existing_fact}"
New information: "{new_info}"

Determine if these contradict each other. Consider:
1. Direct logical contradiction (A vs not A)
2. Updated/superseded information (old version vs new version)
3. Different perspectives on same topic (may not be contradiction)

Output ONLY valid JSON:
{{"contradiction": <true|false>, "type": "<direct|superseded|perspective|none>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>", "action": "<keep_both|supersede_existing|flag_for_review>"}}"""

NRS_SUMMARY_PROMPT = """Summarize the following notes into a concise, well-structured Markdown document.
Focus on key facts, decisions, and current state. Remove outdated or superseded information.

Notes:
{notes}

Output ONLY the Markdown summary. No extra text."""

NRS_LINK_SUGGESTION_PROMPT = """Given a new fact, suggest existing entities it might relate to.

New fact: "{new_fact}"
Category: {category}

Existing entities:
{entities}

Suggest up to {max_suggestions} relevant entity links. Output JSON only:
{{"links": [{{"entity": "<name>", "category": "<category>", "reason": "<why related>"}}]}}"""


@dataclass
class NRSDecision:
    action: str  # recall, remember, both, none
    recall: dict | None = None
    remember: dict | None = None
    contradiction_check: bool = False
    auto_link: bool = True


@dataclass
class ContradictionResult:
    contradiction: bool
    type: str  # direct, superseded, perspective, none
    confidence: float
    reasoning: str
    action: str  # keep_both, supersede_existing, flag_for_review


class NRSOrchestrator:

    def __init__(self, provider_manager, memory_manager):
        self._provider_manager = provider_manager
        self._memory = memory_manager
        self._logger = get_logger("nrs")
        self._enabled = True

    async def decide(self, user_message: str, session_id: str) -> dict[str, Any]:
        default = {"action": "none", "recall": None, "remember": None}

        if not self._enabled:
            return default

        try:
            provider = self._get_nrs_provider()
            if not provider:
                return default

            existing_titles = self._get_existing_titles()
            recent_context = self._get_recent_context(session_id)

            prompt = NRS_USER_PROMPT.format(
                existing_titles=existing_titles,
                recent_context=recent_context,
                user_message=user_message[:2000],
            )

            messages = [
                ChatMessage(role="system", content=NRS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt),
            ]

            response = await provider.chat(
                messages,
                model=NRS_MODEL,
                stream=False,
                temperature=NRS_TEMPERATURE,
            )

            raw = response.message.content if hasattr(response, "message") else str(response)
            raw = (raw or "").strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            decision = json.loads(raw)
            action = decision.get("action", "none")
            recall = decision.get("recall")
            remember = decision.get("remember")

            if action not in ("recall", "remember", "both", "none"):
                action = "none"

            return {
                "action": action,
                "recall": recall if isinstance(recall, dict) else None,
                "remember": remember if isinstance(remember, dict) else None,
            }

        except Exception as e:
            self._logger.debug("NRS decision failed, defaulting to none: %s", e)
            return default

    async def check_contradiction(self, existing_fact: str, new_info: str) -> ContradictionResult:
        default = ContradictionResult(
            contradiction=False, type="none", confidence=0.0,
            reasoning="Check failed", action="keep_both"
        )

        if not self._enabled:
            return default

        try:
            provider = self._get_nrs_provider()
            if not provider:
                return default

            prompt = NRS_CONTRADICTION_PROMPT.format(
                existing_fact=existing_fact[:500],
                new_info=new_info[:500],
            )

            messages = [
                ChatMessage(role="system", content="You are a contradiction detection system."),
                ChatMessage(role="user", content=prompt),
            ]

            response = await provider.chat(
                messages,
                model=NRS_MODEL,
                stream=False,
                temperature=0.1,
            )

            raw = response.message.content if hasattr(response, "message") else str(response)
            raw = (raw or "").strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            return ContradictionResult(
                contradiction=result.get("contradiction", False),
                type=result.get("type", "none"),
                confidence=float(result.get("confidence", 0.0)),
                reasoning=result.get("reasoning", ""),
                action=result.get("action", "keep_both"),
            )

        except Exception as e:
            self._logger.debug("Contradiction check failed: %s", e)
            return default

    async def suggest_links(self, new_fact: str, category: str) -> list[dict]:
        if not self._enabled:
            return []

        try:
            provider = self._get_nrs_provider()
            if not provider:
                return []

            entities = self._get_all_entities_summary()
            prompt = NRS_LINK_SUGGESTION_PROMPT.format(
                new_fact=new_fact[:300],
                category=category,
                entities=entities,
                max_suggestions=3,
            )

            messages = [
                ChatMessage(role="system", content="You suggest relevant entity links for knowledge graphs."),
                ChatMessage(role="user", content=prompt),
            ]

            response = await provider.chat(
                messages,
                model=NRS_MODEL,
                stream=False,
                temperature=0.2,
            )

            raw = response.message.content if hasattr(response, "message") else str(response)
            raw = (raw or "").strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            return result.get("links", [])

        except Exception as e:
            self._logger.debug("Link suggestion failed: %s", e)
            return []

    async def generate_summary(self, notes: str) -> str:
        if not self._enabled:
            return notes[:500] + "..." if len(notes) > 500 else notes

        try:
            provider = self._get_nrs_provider()
            if not provider:
                return notes[:500] + "..." if len(notes) > 500 else notes

            prompt = NRS_SUMMARY_PROMPT.format(notes=notes[:3000])

            messages = [
                ChatMessage(role="system", content="You create concise Markdown summaries of notes."),
                ChatMessage(role="user", content=prompt),
            ]

            response = await provider.chat(
                messages,
                model=NRS_MODEL,
                stream=False,
                temperature=0.3,
            )

            return response.message.content if hasattr(response, "message") else str(response)

        except Exception as e:
            self._logger.debug("Summary generation failed: %s", e)
            return notes[:500] + "..." if len(notes) > 500 else notes

    def _get_nrs_provider(self):
        for provider_id in NRS_PROVIDER_ORDER:
            provider = self._provider_manager.get_provider(provider_id)
            if provider and self._check_model_available(provider_id):
                return provider
        return None

    def _check_model_available(self, provider_id: str) -> bool:
        try:
            models = self._provider_manager.get_models(provider_id)
            return any(m.id == NRS_MODEL for m in models)
        except Exception:
            return False

    async def check_nrs_model_available(self) -> dict:
        results = {}
        for provider_id in NRS_PROVIDER_ORDER:
            try:
                await self._provider_manager.refresh_models(provider_id)
            except Exception:
                pass
            models = self._provider_manager.get_models(provider_id)
            model_ids = {m.id for m in models}
            available = NRS_MODEL in model_ids
            results[provider_id] = {
                "available": available,
                "model": NRS_MODEL,
                "pull_command": f"ollama pull {NRS_MODEL}" if provider_id == "ollama" else f"Configure {provider_id} with model {NRS_MODEL}",
                "provider": provider_id,
            }
            if available:
                return results[provider_id]
        return {
            "available": False,
            "model": NRS_MODEL,
            "pull_command": f"ollama pull {NRS_MODEL} or configure vLLM/OpenAI with model {NRS_MODEL}",
            "provider": "none",
            "details": results,
        }

    def _get_existing_titles(self) -> str:
        try:
            nodes = self._memory.get_neurons()
            if not nodes:
                return "(none)"
            titles = [n.get("title", "untitled") for n in nodes[:30]]
            return ", ".join(titles)
        except Exception:
            return "(unavailable)"

    def _get_all_entities_summary(self) -> str:
        try:
            entities = []
            if hasattr(self._memory, 'second_brain'):
                for cat in getattr(settings.memory.second_brain, "categories", ["projects", "people", "concepts"]):
                    ents = self._memory.second_brain.list_entities(category=cat)
                    for e in ents[:5]:
                        entities.append(f"- {e['name']} ({cat}): {e.get('summary_preview', '')[:100]}")
            return "\n".join(entities[:20]) if entities else "(none)"
        except Exception:
            return "(unavailable)"

    def _get_recent_context(self, session_id: str) -> str:
        try:
            history = self._memory.get_context(limit=6, session_id=session_id)
            if not history:
                return "(no recent messages)"
            lines = []
            for m in history:
                role = m.get("role", "unknown")
                content = (m.get("content", "") or "")[:300]
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    content = " ".join(text_parts)[:300]
                lines.append(f"[{role}] {content}")
            return "\n".join(lines)
        except Exception:
            return "(unavailable)"

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled