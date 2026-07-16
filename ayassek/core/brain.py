from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from ayassek.core.bus import AsyncEventBus
from ayassek.core.events import Event, EventType
from ayassek.core.nrs import NRSOrchestrator
from ayassek.memory.manager import MemoryManager
from ayassek.memory.second_brain import get_second_brain, Fact
from ayassek.memory.rag import get_rag_engine
from ayassek.providers.base import ChatMessage
from ayassek.providers.manager import ProviderManager
from ayassek.reasoning.executor import ActionExecutor
from ayassek.reasoning.planner import AdvancedPlanner
from ayassek.reasoning.reflection import ReflectionLoop
from ayassek.utils.logging import get_logger


SYSTEM_PROMPT = """You are Ayassek, a multimodal general brain agent — the central coordination layer of a robotics and AI system.

## Your Role
You think, plan, reason, and act. You are NOT just a chatbot — you are an operational agent with real tools.
When a user asks you to DO something, you MUST use tools to accomplish it. Do not just describe what you would do — actually do it.

## Tool Calling Protocol
You have access to tools via the OpenAI function-calling protocol (the `tool_calls` channel).
When you want to use a tool, emit a structured tool_call with the exact tool name and valid JSON arguments.
Do NOT write tool calls as text in your response — use the `tool_calls` field.
If you are unsure which tool to use, pick the closest match based on the descriptions below.
Always wait for the tool result before continuing your response.

## Available Tools

### System & Code
- **run_command** — Execute a shell command directly on the host system.
  Required: `command` (string). Optional: `timeout` (int, default 30s).
  Use for: ls, cat, grep, find, mkdir, git, curl, system commands on the HOST.

- **run_code** — Execute Python or shell scripts in a sandboxed container (podman).
  Required: `code` (string). Optional: `language` ("python"|"sh", default "python"), `timeout` (int, default 30s).
  Use for: running Python scripts, multi-step shell scripts that need isolation.
  NOTE: `language="bash"` is NOT supported — use `language="sh"` instead.

- **system_info** — Get system information (OS, CPU, memory, disk). No parameters needed.

### Web
- **web_search** — Search the web via DuckDGo. Returns text summaries.
  Required: `query` (string). Optional: `max_results` (int, default 5, max 10).

- **browser** — Read web page content with a headless browser. Supports read/click/type/screenshot.
  Required: `url` (string). Optional: `action` ("read"|"click"|"type"|"screenshot", default "read"), `selector` (string), `value` (string).
  Use for: extracting text from web pages, interacting with page elements.
  This is DIFFERENT from web_search — use browser when you need full page content.

### Memory — Short-term (current session only)
- **remember** — Store a key-value pair in short-term memory. DIES AFTER SESSION ENDS.
  Required: `key` (string), `value` (string).
  USE ONLY FOR: temporary session variables — `user_language=pt`, `current_topic=math`, `temp_result=42`.
  NEVER USE FOR: facts about people, projects, decisions, preferences, or anything that should persist.

- **recall** — Retrieve a value from short-term memory by key.
  Required: `key` (string).

### Memory — Long-term (persistent, survives sessions)
- **rag_query** — Search the RAG knowledge base (ingested documents, uploaded files).
  Required: `query` (string). Optional: `top_k` (int, default 5).
  Use when the user asks about something from ingested documents or past reference materials.

- **brain_search** — Search the Second Brain knowledge graph (entities, facts about people/projects/concepts).
  Required: `query` (string). Optional: `category` ("projects"|"people"|"concepts"|"meetings"|"references"|"tasks").
  Use when the user asks about people, projects, concepts — or when NRS recall context is insufficient.

### Files (workspace: /home/drp27/Ayassek)
- **file_read** — Read file contents. Required: `path` (string, relative to workspace).
- **file_write** — Write content to a file. Required: `path` (string), `content` (string).
- **file_list** — List files in a directory. Optional: `path` (string, default "."), `pattern` (string).
- **file_glob** — Find files matching a glob pattern. Required: `pattern` (string). Optional: `root`, `max_results`.
- **file_grep** — Search file contents with regex. Required: `pattern` (string). Optional: `glob`, `root`, `max_results`.
  NOTE: All file paths are relative to /home/drp27/Ayassek. Absolute paths outside this directory are rejected.

### Voice
- **voice_speak** — Text-to-speech. Required: `text` (string). Optional: `voice` (default "af_heart"), `speed` (float 0.5-2.0).
- **voice_transcribe** — Speech-to-text from audio. Required: `audio_b64` (base64 WAV). Optional: `language`.

## Memory Strategy — CRITICAL RULES

### Como funciona o NRS (Neural Recall System)
O NRS é um modelo pequeno (qwen2.5:1.5b) que roda ANTES de cada resposta sua. Ele analisa a mensagem do usuário e decide:
- `remember` → cria neuron + entity + fact no Second Brain/GraphDB/RAG **automaticamente** (código Python, não você)
- `recall` → busca contexto relevante e **injeta no seu system prompt**
- `both` → faz ambos
- `none` → nada

**VOCÊ NÃO ARMAZENA FATOS PERSISTENTES. O NRS FAZ ISSO.**
Mas você DEVE buscar ativamente quando o NRS não encontrou algo.

### O que o NRS detecta para armazenar:
- Comandos explícitos: "lembre-se", "anote", "salve", "guarde", "remember", "note", "save"
- Informações pessoais: nomes, preferências, cargos, contactos
- Informações de projeto: decisões, prazos, arquitetura, dependências
- Factos técnicos: APIs, configs, versões, comandos, workflows

### REGRA DE OURO — armazenamento
**NUNCA use a ferramenta `remember` para fatos sobre pessoas, projetos, ou qualquer coisa que deva persistir.**
**Use `remember` APENAS para variáveis efémeras desta sessão.**

### REGRA DE OURO — busca
**SEMPRE que o usuário perguntar sobre algo que o NRS deveria saber mas o contexto injetado parece insuficiente, use `brain_search` ou `rag_query` ativamente.**
**Não assuma que o NRS encontrou tudo. Verifique se o contexto cobre a pergunta.**

---

### DIFERENÇA ENTRE AS FERRAMENTAS DE MEMÓRIA

| Ferramenta | Quem chama? | Escopo | Persiste? |
|------------|-------------|--------|-----------|
| `remember` | **VOCÊ** (LLM) | Sessão atual | ❌ Morre com a sessão |
| `recall` | **VOCÊ** (LLM) | Sessão atual | ❌ |
| `brain_search` | **VOCÊ** (LLM) | Second Brain | ✅ Persistente |
| `rag_query` | **VOCÊ** (LLM) | Documentos/RAG | ✅ Persistente |
| NRS `remember` | **CÓDIGO PYTHON** | Second Brain + GraphDB + RAG | ✅ Persistente |
| NRS `recall` | **CÓDIGO PYTHON** | Contexto injetado no prompt | — |
---

### Examples — CORRECT behavior

✅ **NRS decides `remember` — you respond naturally (NO tool call for storage):**
User: "João gosta de café preto e trabalha no backend"
NRS: {action: "remember", ...} → armazenado automaticamente pelo código
You:   "Entendido. João prefere café preto e está no backend."  ← apenas responda

✅ **NRS injects recall context — answer from it (NO tool call needed):**
User: "O que o João gosta de beber?"
Your prompt has: "## Retrieved context... João gosta de café preto"
You:   "João gosta de café preto."  ← responda direto, contexto já está no prompt

✅ **NRS recall insuficiente — use brain_search PROACTIVELY:**
User: "Quem é o João mesmo? Não me lembro."
Your prompt has NRS context but it seems incomplete or empty.
You:   brain_search(query="João")  ← ✅ BUSQUE ATIVAMENTE
You:   "João é desenvolvedor backend, gosta de café preto." (baseado nos resultados)

✅ **Temporary session variable — use remember:**
User: "Vamos debugar em português"
You:   remember(key="user_language", value="pt")  ← variável de sessão ✅
You:   "Certo, debugando em português."

✅ **User references a document — use rag_query:**
User: "O que dizia aquele PDF sobre o projeto Alpha?"
You:   rag_query(query="projeto Alpha")  ← ✅ busca em documentos
You:   "Segundo o PDF, o projeto Alpha..." (baseado nos resultados)

❌ **WRONG — NUNCA use `remember` para fatos persistentes:**
User: "Meu nome é Maria e sou designer"
You:   remember(key="user_name", value="Maria")  ← ❌ ERRADO! NRS armazena isso
You:   "Prazer, Maria!"                          ← ✅ resposta correta, mas tool call foi errado

### REGRA PARA `brain_search` e `rag_query` — USE ATIVAMENTE
Estas são SUAS ferramentas. Use-as sempre que:
- O usuário pergunta sobre algo do passado e o contexto NRS parece vazio ou incompleto
- O usuário referencia uma pessoa, projeto, ou conceito específico → `brain_search`
- O usuário referencia um documento, PDF, ou material ingerido → `rag_query`
- O usuário diz "você lembra de..." e o contexto NRS não cobre → `brain_search` + `rag_query` (ambos!)
- O usuário pergunta "o que sabe sobre X?" → `brain_search` primeiro, depois `rag_query`

**NÃO espere o NRS. Se o contexto injetado é insuficiente, BUSQUE VOCÊ MESMO.**

## Guidelines
- Be precise, direct, and helpful. Answer in the user's language.
- USE TOOLS when the user asks you to DO something. Do not just describe — ACT.
- Think about what you know vs what you need to find out.
- If a tool returns an error, analyze it and try an alternative approach.
- Process tool results carefully before responding.
- For shell commands, prefer `run_command` (host) for simple one-liners.
- For multi-step Python or scripts needing isolation, use `run_code`.
- When reading or writing files, paths are relative to /home/drp27/Ayassek.

You are running as Ayassek v1.0 on a single Linux system."""

SUMMARY_PROMPT = """Summarize the following conversation concisely. Keep key facts, decisions, entities, and outcomes.
Discard greetings, filler, and repetition. Use bullet points.
Output language: same as input.

CONVERSATION:
{messages}

SUMMARY:"""

MAX_TOOL_LOOP_ITERATIONS = 5
SUMMARY_TRIGGER_INTERVAL = 20
SUMMARY_MODEL = "qwen2.5:1.5b"
SUMMARY_TEMPERATURE = 0.3


class AyassekBrain:
    def __init__(
        self,
        event_bus: AsyncEventBus,
        provider_manager: ProviderManager,
        memory_manager: MemoryManager,
        tool_executor: ActionExecutor,
        planner: AdvancedPlanner,
        reflection: ReflectionLoop,
        nrs_orchestrator: NRSOrchestrator | None = None,
    ):
        self._bus = event_bus
        self._provider_manager = provider_manager
        self._memory = memory_manager
        self._executor = tool_executor
        self._planner = planner
        self._reflection = reflection
        self._nrs = nrs_orchestrator
        self._logger = get_logger("brain")
        self._summarize_semaphore = asyncio.Semaphore(2)
        self._background_tasks: set[asyncio.Task] = set()

    def _track_task(self, task: asyncio.Task):
        self._background_tasks.add(task)
        task.add_done_callback(lambda t: (
            self._background_tasks.discard(t),
            t.exception() if not t.cancelled() else None,
        ))

    async def process_message(
        self,
        content: str,
        session_id: str = "default",
        images: list[str] | None = None,
    ):
        await self._bus.emit(Event(
            type=EventType.USER_MESSAGE,
            data={"content": content, "images": images},
            session_id=session_id,
        ))

        await self._bus.emit(Event(
            type=EventType.BRAIN_THINKING,
            data={"status": "processing"},
            session_id=session_id,
        ))

        try:
            provider = self._provider_manager.get_active_provider()
            if not provider:
                await self._emit_error(session_id, "No active provider configured.")
                return

            model = self._provider_manager.get_active_model()
            tools = self._executor.get_openai_tools() if provider.supports_tools() else None

            self._memory.add_message("user", content, session_id=session_id, images=images)
            history = self._memory.get_context(limit=29, session_id=session_id)

            nrs_decision = await self._apply_nrs_orchestration(content, session_id)

            system_content = self._build_system_prompt_with_context(session_id, nrs_decision.get("recall_result"))
            messages = [ChatMessage(role="system", content=system_content)]
            for msg in history:
                images_data = []
                if msg.get("images") and isinstance(msg["images"], list):
                    for img_data in msg["images"]:
                        images_data.append({
                            "type": "image_url",
                            "image_url": {"url": img_data},
                        })
                if images_data:
                    msg_content = msg.get("content", "")
                    if isinstance(msg_content, str):
                        content_block = [{"type": "text", "text": msg_content}] + images_data
                        messages.append(ChatMessage(role=msg["role"], content=content_block))
                    else:
                        messages.append(ChatMessage(role=msg["role"], content=msg_content))
                else:
                    messages.append(ChatMessage(role=msg["role"], content=msg.get("content", "")))

            if images:
                image_blocks = []
                for img_data in images:
                    image_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": img_data},
                    })
                last_msg = messages[-1]
                if isinstance(last_msg.content, str):
                    content_block = [{"type": "text", "text": last_msg.content}] + image_blocks
                    messages[-1] = ChatMessage(role=last_msg.role, content=content_block)
                elif isinstance(last_msg.content, list):
                    messages[-1] = ChatMessage(role=last_msg.role, content=[*last_msg.content, *image_blocks])

            use_stream = provider.supports_streaming()

            if use_stream:
                full_response = await self._process_stream(messages, model, tools, session_id)
            else:
                full_response = await self._process_non_stream(messages, model, tools, session_id)

            self._memory.add_message("assistant", full_response, session_id=session_id)

            msg_count = self._memory.get_session_message_count(session_id)
            if msg_count >= SUMMARY_TRIGGER_INTERVAL and msg_count % SUMMARY_TRIGGER_INTERVAL == 0:
                task = asyncio.create_task(self._maybe_summarize(session_id))
                self._track_task(task)

            nrs_remember = nrs_decision.get("remember")
            if nrs_remember and nrs_decision["action"] in ("remember", "both"):
                title = nrs_remember.get("title", "").strip()
                content = nrs_remember.get("content", "").strip()
                if title and content:
                    task = asyncio.create_task(self._run_nrs_remember(title, content, session_id))
                    self._track_task(task)

            await self._bus.emit(Event(
                type=EventType.BRAIN_DONE,
                data={"status": "completed"},
                session_id=session_id,
            ))

        except Exception as e:
            self._logger.exception("Brain processing error")
            await self._emit_error(session_id, str(e))

    async def _apply_nrs_orchestration(self, content: str, session_id: str) -> dict:
        rag_engine = get_rag_engine()
        second_brain = get_second_brain()

        rag_context = ""
        sb_context = ""

        if self._nrs is None:
            decision = {"action": "none", "recall": None, "remember": None}
        else:
            try:
                decision = await self._nrs.decide(content, session_id)
            except Exception as e:
                self._logger.debug("NRS orchestration failed: %s", e)
                decision = {"action": "none", "recall": None, "remember": None}

        query = content
        recall_text = None
        if decision.get("recall") and decision["action"] in ("recall", "both"):
            try:
                query = decision["recall"].get("query", content)
                n_results = decision["recall"].get("n_results", 5)

                rag_result = rag_engine.query(query, top_k=max(n_results, 10), rerank=True)
                if rag_result.reranked:
                    lines = ["## Retrieved from RAG:"]
                    for i, r in enumerate(rag_result.reranked):
                        src = r.get("source", "unknown")
                        txt = r.get("text", "")[:300]
                        lines.append(f"[{i+1}] Source: {src}\n{txt}")
                    rag_context = "\n\n---\n\n".join(lines)

                sb_results = second_brain.search_facts(query, top_k=n_results)
                if sb_results:
                    lines = ["## Retrieved from Second Brain:"]
                    for i, r in enumerate(sb_results):
                        ent = r.get("entity", "unknown")
                        cat = r.get("category", "general")
                        txt = r.get("text", "")[:300]
                        lines.append(f"[{i+1}] {ent} ({cat}): {txt}")
                    sb_context = "\n\n---\n\n".join(lines)

            except Exception as e:
                self._logger.debug("Enhanced NRS recall failed: %s", e)

        combined_context = ""
        if rag_context:
            combined_context += rag_context
        if sb_context:
            if combined_context:
                combined_context += "\n\n---\n\n"
            combined_context += sb_context

        # Fallback: if recall was requested but neither RAG nor SB returned results
        if not combined_context and decision.get("recall") and decision["action"] in ("recall", "both"):
            try:
                all_entities = second_brain.list_entities()
                query_lower = query.lower()
                matched = []
                for e in all_entities:
                    if query_lower in e["name"].lower():
                        matched.append(e)
                if matched:
                    lines = ["## Retrieved (fallback — entity name match):"]
                    for e in matched:
                        lines.append(f"- **{e['name']}** ({e['category']})")
                        if e.get("summary_preview"):
                            lines.append(f"  {e['summary_preview']}")
                    combined_context = "\n".join(lines)
            except Exception as e:
                self._logger.debug("Fallback entity search failed: %s", e)

        # Emit NRS_RECALLED event if recall found results
        if combined_context and decision.get("recall") and decision["action"] in ("recall", "both"):
            try:
                rag_count = len(rag_result.reranked) if rag_result.reranked else 0
                sb_count = len(sb_results) if sb_results else 0
                await self._bus.emit(Event(
                    type=EventType.NRS_RECALLED,
                    data={"query": query, "rag_results": rag_count, "sb_results": sb_count},
                    session_id=session_id,
                ))
            except Exception:
                pass

        return {**decision, "recall_result": combined_context, "rag_context": rag_context, "sb_context": sb_context}

    async def _run_nrs_remember(self, title: str, content: str, session_id: str):
        import random
        neuron_x = random.uniform(100, 600)
        neuron_y = random.uniform(100, 400)
        try:
            node = self._memory.create_neuron(title=title, content=content, x=neuron_x, y=neuron_y)
            if node and isinstance(node, dict):
                neuron_x = node.get("x", neuron_x)
                neuron_y = node.get("y", neuron_y)
            self._logger.info("NRS auto-remembered: %s", title)
        except Exception as e:
            self._logger.debug("NRS remember (neuron) failed: %s", e)

        try:
            rag_engine = get_rag_engine()
            second_brain = get_second_brain()

            category = "concepts"
            title_lower = title.lower()
            if "project" in title_lower:
                category = "projects"
            elif "person" in title_lower or "people" in title_lower or "user" in title_lower or "name" in title_lower:
                category = "people"
            elif "meeting" in title_lower or "call" in title_lower or "discussion" in title_lower:
                category = "meetings"
            elif "reference" in title_lower or "doc" in title_lower or "link" in title_lower or "article" in title_lower:
                category = "references"
            elif "task" in title_lower or "todo" in title_lower or "action" in title_lower:
                category = "tasks"
            elif "concept" in title_lower or "topic" in title_lower or "idea" in title_lower:
                category = "concepts"

            entity_name = title.replace(":", "").strip() or "nrs_memory"
            entity = second_brain.get_entity(category, entity_name)
            if entity is None:
                entity = second_brain.create_entity(category, entity_name, content, x=neuron_x, y=neuron_y)

            fact = Fact(
                id=str(uuid.uuid4())[:8],
                text=content,
                category=category,
                tags=["nrs", "auto"],
                source="nrs",
                status="active",
            )
            second_brain.add_fact(category, entity_name, fact)

            rag_engine.ingest_text(
                text=content,
                source=f"nrs:{entity_name}",
                category=f"second_brain_{category}",
                tags=["nrs", "auto"],
                metadata={"entity": entity_name, "title": title, "type": "fact"},
            )

            self._logger.info("NRS auto-remembered to Second Brain: %s/%s", category, entity_name)

            # Emit real-time events for frontend
            try:
                from ayassek.core.events import Event, EventType
                await self._bus.emit(Event(
                    type=EventType.NRS_REMEMBERED,
                    data={"title": title, "content": content, "entity_name": entity_name, "category": category, "x": neuron_x, "y": neuron_y},
                    session_id=session_id,
                ))
                await self._bus.emit(Event(
                    type=EventType.ENTITY_CREATED,
                    data={"name": entity_name, "category": category, "summary": content, "x": neuron_x, "y": neuron_y},
                    session_id=session_id,
                ))
                await self._bus.emit(Event(
                    type=EventType.FACT_ADDED,
                    data={"entity_name": entity_name, "category": category, "text": content, "tags": ["nrs", "auto"], "status": "active"},
                    session_id=session_id,
                ))
            except Exception:
                pass
        except Exception as e:
            self._logger.debug("NRS remember (second brain) failed: %s", e)

    def _build_system_prompt_with_context(
        self, current_session_id: str, nrs_recall_result: str | None = None
    ) -> str:
        base = SYSTEM_PROMPT
        summaries = self._memory.get_all_session_summaries(exclude_session_id=current_session_id)
        parts = [base]

        # Inject dynamic tool list (in case tools were added/removed at runtime)
        try:
            tools = self._executor.get_openai_tools()
            if tools:
                tool_lines = ["## Registered Tools (live)"]
                for t in tools:
                    fn = t.get("function", {})
                    name = fn.get("name", "?")
                    desc = fn.get("description", "")
                    params = fn.get("parameters", {}).get("properties", {})
                    required = fn.get("parameters", {}).get("required", [])
                    param_str = ", ".join(
                        f'{k}: {"required" if k in required else "optional"} ({v.get("type", "any")})'
                        for k, v in params.items()
                    )
                    tool_lines.append(f"- {name}({param_str}) — {desc}")
                parts.append("\n".join(tool_lines))
        except Exception:
            pass

        if nrs_recall_result:
            parts.append("\n## Retrieved context (RAG + Second Brain):\n" + nrs_recall_result)
        if summaries:
            parts.append("## Context from other sessions:\n")
            for s in summaries:
                name = s.get("name", s.get("id", "Unknown"))
                parts.append(f"### {name}")
                parts.append(s.get("summary", ""))
        return "\n\n".join(parts)

    async def _maybe_summarize(self, session_id: str):
        async with self._summarize_semaphore:
            try:
                self._logger.info("Generating summary for session %s", session_id)
                history = self._memory.get_message_history(session_id, limit=40)
                if not history:
                    return

                dialog = []
                for m in history:
                    role = m.get("role", "unknown")
                    text = (m.get("content", "") or "")[:800]
                    dialog.append(f"[{role}] {text}")
                convo_text = "\n".join(dialog)

                prompt = SUMMARY_PROMPT.format(messages=convo_text)
                messages = [ChatMessage(role="user", content=prompt)]

                provider = self._provider_manager.get_active_provider()
                summary = None

                if provider:
                    try:
                        response = await provider.chat(
                            messages,
                            model=SUMMARY_MODEL,
                            stream=False,
                            temperature=SUMMARY_TEMPERATURE,
                        )
                        summary = response.message.content if hasattr(response, "message") else str(response)
                    except Exception as e:
                        self._logger.warning("Summary with active provider failed, trying ollama: %s", e)

                if summary is None:
                    try:
                        ollama_provider = self._provider_manager.get_provider("ollama")
                        if ollama_provider:
                            response = await ollama_provider.chat(
                                messages,
                                model=SUMMARY_MODEL,
                                stream=False,
                                temperature=SUMMARY_TEMPERATURE,
                            )
                            summary = response.message.content if hasattr(response, "message") else str(response)
                        else:
                            self._logger.warning("No provider available for summary generation")
                            return
                    except Exception as e2:
                        self._logger.warning("Ollama fallback for summary also failed: %s", e2)
                        return

                summary = (summary or "").strip()
                if not summary:
                    return

                self._memory.update_session_summary(session_id, summary)
                self._logger.info("Summary saved for session %s (%d chars)", session_id, len(summary))

                try:
                    self._memory.create_neuron(
                        title=f"Summary: {session_id}",
                        content=summary,
                    )
                    self._logger.info("Neuron created from session %s summary", session_id)
                except Exception as e:
                    self._logger.warning("Failed to create neuron from summary: %s", e)

            except Exception as e:
                self._logger.warning("Summary generation failed: %s", e)

    async def _execute_tool_calls(
        self,
        pending_tool_calls: list[dict[str, Any]],
        session_id: str,
    ) -> dict[str, str]:
        tool_results: dict[str, str] = {}
        for tc in pending_tool_calls:
            tool_name = tc["function"]["name"]
            tool_id = tc["id"]
            try:
                tool_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                raw_args = tc["function"].get("arguments", "")
                tool_results[tool_id] = (
                    f"Error: Your tool call arguments for '{tool_name}' were not valid JSON. "
                    f"Received: {raw_args[:200]}. "
                    f"Please resend the tool call with valid JSON arguments."
                )
                continue

            await self._bus.emit(Event(
                type=EventType.BRAIN_TOOL_CALL,
                data={"tool": tool_name, "args": tool_args},
                session_id=session_id,
            ))

            result = await self._executor.execute_tool(tool_name, tool_args)
            tool_results[tool_id] = result

            await self._bus.emit(Event(
                type=EventType.BRAIN_TOOL_RESULT,
                data={"tool": tool_name, "result": result},
                session_id=session_id,
            ))
        return tool_results

    def _build_tool_followup_messages(
        self,
        messages: list[ChatMessage],
        pending_tool_calls: list[dict[str, Any]],
        tool_results: dict[str, str],
    ) -> list[ChatMessage]:
        result = list(messages)
        result.append(ChatMessage(
            role="assistant",
            content="",
            tool_calls=pending_tool_calls,
        ))
        for tc in pending_tool_calls:
            result.append(ChatMessage(
                role="tool",
                content=tool_results.get(tc["id"], ""),
                tool_call_id=tc["id"],
            ))
        return result

    async def _process_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        tools: list[dict[str, Any]] | None,
        session_id: str,
    ) -> str:
        provider = self._provider_manager.get_active_provider()
        full_text = ""
        current_messages = messages

        for iteration in range(MAX_TOOL_LOOP_ITERATIONS):
            tool_call_buffer: dict[int, dict[str, Any]] = {}

            stream = await provider.chat(current_messages, model=model, stream=True, tools=tools)
            async for chunk in stream:
                if chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        idx = tc.get("index", 0)
                        if idx not in tool_call_buffer:
                            tool_call_buffer[idx] = {
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:12]}"),
                                "function": {"name": "", "arguments": ""},
                            }
                        if "id" in tc:
                            tool_call_buffer[idx]["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            tool_call_buffer[idx]["function"]["name"] = tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            tool_call_buffer[idx]["function"]["arguments"] += tc["function"]["arguments"]

                if chunk.token:
                    full_text += chunk.token
                    await self._bus.emit(Event(
                        type=EventType.BRAIN_TOKEN,
                        data={"token": chunk.token, "text": full_text},
                        session_id=session_id,
                    ))

                if chunk.finish_reason:
                    break

            pending_tool_calls = list(tool_call_buffer.values()) if tool_call_buffer else []

            if not pending_tool_calls:
                break

            tool_results = await self._execute_tool_calls(pending_tool_calls, session_id)
            current_messages = self._build_tool_followup_messages(current_messages, pending_tool_calls, tool_results)

        if not full_text.strip() and current_messages != messages:
            tool_summary_parts = []
            for tc in pending_tool_calls or []:
                name = tc.get("function", {}).get("name", "tool")
                tool_summary_parts.append(name)
            if tool_summary_parts:
                full_text = f"[Used tools: {', '.join(tool_summary_parts)}]"

        await self._bus.emit(Event(
            type=EventType.BRAIN_RESPONSE,
            data={"text": full_text},
            session_id=session_id,
        ))

        return full_text

    async def _process_non_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        tools: list[dict[str, Any]] | None,
        session_id: str,
    ) -> str:
        provider = self._provider_manager.get_active_provider()
        current_messages = messages
        text = ""
        had_tool_calls = False

        for iteration in range(MAX_TOOL_LOOP_ITERATIONS):
            response = await provider.chat(current_messages, model=model, stream=False, tools=tools)

            if hasattr(response, "message"):
                msg_content = response.message.content if response.message.content else ""
            else:
                text = str(response)
                break

            if not (hasattr(response, "message") and response.message.tool_calls):
                text = msg_content
                break

            had_tool_calls = True
            tool_results: dict[str, str] = {}
            for tc in response.message.tool_calls:
                tool_name = tc["function"]["name"]
                tool_id = tc.get("id", f"call_{uuid.uuid4().hex[:12]}")

                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    raw_args = tc["function"].get("arguments", "")
                    tool_results[tool_id] = (
                        f"Error: Your tool call arguments for '{tool_name}' were not valid JSON. "
                        f"Received: {raw_args[:200]}. "
                        f"Please resend the tool call with valid JSON arguments."
                    )
                    continue

                await self._bus.emit(Event(
                    type=EventType.BRAIN_TOOL_CALL,
                    data={"tool": tool_name, "args": tool_args},
                    session_id=session_id,
                ))

                result = await self._executor.execute_tool(tool_name, tool_args)
                tool_results[tool_id] = result

                await self._bus.emit(Event(
                    type=EventType.BRAIN_TOOL_RESULT,
                    data={"tool": tool_name, "result": result},
                    session_id=session_id,
                ))

            tool_messages = list(current_messages)
            tool_messages.append(ChatMessage(
                role="assistant",
                content="",
                tool_calls=response.message.tool_calls,
            ))
            for tc in response.message.tool_calls:
                tool_id = tc.get("id", f"call_{uuid.uuid4().hex[:12]}")
                tool_messages.append(ChatMessage(
                    role="tool",
                    content=tool_results.get(tool_id, ""),
                    tool_call_id=tool_id,
                ))
            current_messages = tool_messages
            text = msg_content

        if not text.strip() and had_tool_calls:
            tool_names = []
            for tc in response.message.tool_calls if hasattr(response, "message") and response.message.tool_calls else []:
                tool_names.append(tc.get("function", {}).get("name", "tool"))
            if tool_names:
                text = f"[Used tools: {', '.join(tool_names)}]"

        await self._bus.emit(Event(
            type=EventType.BRAIN_RESPONSE,
            data={"text": text},
            session_id=session_id,
        ))

        return text

    async def _emit_error(self, session_id: str, error: str):
        await self._bus.emit(Event(
            type=EventType.BRAIN_ERROR,
            data={"error": error},
            session_id=session_id,
        ))