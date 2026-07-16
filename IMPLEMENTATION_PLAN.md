# Ayassek Implementation Plan — Phases 2-5

**Status**: Phase 1 Complete (RAG + Second Brain + Enhanced NRS)
**Priority Order**: 5 → 4 → 3 → 2 (ROS2 Cancelled)
**Timeline**: 6 weeks

---

## Phase 5: Second Brain & RAG UI + Bug Fixes (Week 1-2)

### 5.1 Critical Bug Fixes (Day 1)

| Bug | Files | Fix |
|-----|-------|-----|
| `settings.rag` AttributeError | `embeddings.py:29-33,80`, `rag.py:38-41,278-280`, `reranker.py:29-38`, `chunker.py:270` | Change to `settings.memory.rag` |
| `settings.second_brain` AttributeError | `nrs.py:337` | Change to `settings.memory.second_brain` |
| `lancedb` not installed | `requirements.txt` | `pip install lancedb>=0.6.0` in venv |
| Duplicate dependencies | `requirements.txt` lines 13-21 | Deduplicate |
| `settings.rag.reranker.device` / `low_latency_mode` missing | `reranker.py:31,38` | Add to `RerankerConfig` in settings.py & defaults.yaml |
| `settings.rag.embedding.instruction_aware` / `max_length` missing | `embeddings.py:32,33` | Add to `EmbeddingConfig` |

### 5.2 Frontend Migration: React + TypeScript + Vite + Tailwind (Day 2-3)

**New Structure:**
```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Footer.tsx
│   │   ├── Chat/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── StreamingText.tsx
│   │   │   ├── ToolIndicator.tsx
│   │   │   └── InputArea.tsx
│   │   ├── Memory/
│   │   │   ├── NeuralGraph.tsx          (React Flow)
│   │   │   ├── SecondBrainPanel.tsx     (NEW)
│   │   │   ├── RAGStatusPanel.tsx       (NEW)
│   │   │   ├── EntityEditor.tsx         (NEW)
│   │   │   └── FactEditor.tsx           (NEW)
│   │   ├── Providers/
│   │   ├── Tools/
│   │   ├── Logs/
│   │   └── Settings/
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useChat.ts
│   │   ├── useMemory.ts
│   │   └── useProviders.ts
│   ├── services/
│   │   ├── api.ts
│   │   └── ws.ts
│   ├── types/
│   │   ├── api.ts
│   │   ├── memory.ts
│   │   └── chat.ts
│   └── utils/
│       ├── markdown.ts
│       └── format.ts
└── public/
```

**Dependencies:**
```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "react-router-dom": "^6.20.0",
  "@xyflow/react": "^12.0.0",
  "@tanstack/react-query": "^5.0.0",
  "zustand": "^4.4.0",
  "marked": "^11.0.0",
  "dompurify": "^3.0.0",
  "react-syntax-highlighter": "^15.5.0",
  "axios": "^1.6.0",
  "clsx": "^2.0.0"
}
```

### 5.3 Second Brain Panel (Day 3-4)

**Components & Features:**
- **Entity Tree** — Collapsible by category (projects, people, concepts, meetings, references, tasks)
- **Entity Detail** — Markdown editor for `summary.md`, fact list with status badges (active/superseded/contradicted/uncertain)
- **Fact Editor** — Inline add/edit/delete, tags, source, version history (accordion)
- **Search Bar** — Semantic search via `POST /api/brain/search`, filter by category
- **Graph View** — Entities as nodes, facts/links as edges (React Flow)
- **Index to Vectors** button — Triggers `POST /api/brain/index`

**API Endpoints:**
```
GET    /api/brain/entities?category=
GET    /api/brain/entities/{category}/{name}
POST   /api/brain/entities
PUT    /api/brain/entities/{category}/{name}
DELETE /api/brain/entities/{category}/{name}
POST   /api/brain/entities/{category}/{name}/facts
PUT    /api/brain/entities/{category}/{name}/facts/{fact_id}
DELETE /api/brain/entities/{category}/{name}/facts/{fact_id}
POST   /api/brain/search
POST   /api/brain/index
GET    /api/brain/stats
```

### 5.4 RAG Status Panel (Day 4-5)

**Components & Features:**
- **Index Stats** — Vector count, table size, last indexed, embedding/reranker model status
- **Ingestion Controls** — Text area + source/category/tags, file upload (drag-drop), REPOSTOINSPIRE ingest button
- **Pipeline Híbrido:**
  - Digital PDFs → `marker` (better OCR, structure preservation)
  - Scanned PDFs → `pdf2image` + Qwen3-VL (vision analysis)
  - Auto-detect: text layer presence → choose pipeline
- **Query Tester** — Input query, show top-k chunks with scores, rerank toggle
- **Index Management** — Create HNSW index, full reindex, delete by source
- **Pipeline Status** — Embedding model loaded, reranker loaded, LanceDB connected

**API Endpoints:**
```
GET    /api/rag/status
POST   /api/rag/ingest
POST   /api/rag/query
POST   /api/rag/ingest/repostoinpire
POST   /api/rag/index/create
POST   /api/rag/reindex
DELETE /api/rag/source/{path}
```

### 5.5 Neural Graph Migration to React Flow (Day 5)

- Replace vanilla canvas/SVG with `@xyflow/react`
- Preserve: drag, pan, zoom, create node, connect nodes, edit modal
- Add: mini-map, controls panel, layout algorithms (dagre/elkjs)
- Nodes = neurons, Edges = synapses (manual vs auto styling)

### 5.6 Chat Panel Polish (Day 6)

- Streaming tokens via WebSocket (existing)
- Image upload preview (prep for Phase 2)
- Tool call visualization (expandable details)
- Session sidebar (existing)
- Markdown rendering with code highlighting (`react-syntax-highlighter`)

### 5.7 Build & Integration (Day 7)

- `npm run build` → outputs to `ayassek/interfaces/web/static/`
- Update `app.py` StaticFiles mount
- Verify all WebSocket events work with React frontend
- TypeScript strict mode, ESLint, Prettier

---

## Phase 4: Voice I/O — Local STT/TTS (Week 3)

### 4.1 STT — faster-whisper (Day 1-2)

```python
# ayassek/memory/voice/stt.py
class STTService:
    def __init__(self, model="base", device="auto", compute_type="int8"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model, device=device, compute_type=compute_type)
    
    def transcribe(self, audio_path: str, language: str = "pt") -> str:
        segments, _ = self.model.transcribe(audio_path, language=language)
        return " ".join(s.text for s in segments)
    
    async def transcribe_streaming(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        # VAD + streaming transcription
        pass
```

- Models: `tiny` (39MB), `base` (74MB), `small` (244MB), `medium` (769MB)
- Default: `base` for speed, configurable via settings
- Languages: Portuguese + English (configurable)

### 4.2 TTS — Kokoro-82M (Day 2-3)

```python
# ayassek/memory/voice/tts.py
class TTSService:
    def __init__(self, lang_code='a', voice='af_heart'):
        from kokoro import KPipeline
        self.pipeline = KPipeline(lang_code=lang_code)
        self.voice = voice
    
    def synthesize(self, text: str, output_path: str) -> str:
        generator = self.pipeline(text, voice=self.voice)
        for i, (gs, ps, audio) in enumerate(generator):
            sf.write(output_path, audio, 24000)
        return output_path
    
    async def synthesize_streaming(self, text: str) -> AsyncIterator[bytes]:
        # Stream audio chunks for real-time playback
        pass
```

- Apache-licensed, 82M params, fast CPU inference
- Voices: `af_heart`, `af_bella`, `af_sarah`, `am_michael`, `am_adam` (EN), `pf_dora` (PT-BR)
- Requires `espeak-ng` system dependency

### 4.3 Voice Tools (Day 3)

```python
# ayassek/tools/builtins/voice_tools.py
class VoiceRecordTool(BaseTool):       # Record from mic, return base64
class VoiceTranscribeTool(BaseTool):   # STT on base64 audio
class VoiceSpeakTool(BaseTool):        # TTS text → play audio
```

### 4.4 Frontend Voice UI (Day 4)

- **Mic Button** in chat input — hold to record, release to send
- **Waveform Visualizer** during recording (Web Audio API + Canvas)
- **Play Button** on assistant messages — TTS playback with progress
- **Voice Settings** panel — STT model size, TTS voice, language, VAD sensitivity
- **Audio Context** management (autoplay policy handling)

### 4.5 Integration (Day 5)

- WebSocket binary frames for audio streaming
- `POST /api/voice/transcribe` and `POST /api/voice/synthesize` endpoints
- Auto-detect `faster-whisper` and `kokoro` availability at startup
- Settings in `defaults.yaml` under `voice` section

---

## Phase 3: Advanced Reasoning & Tools (Week 4-5)

### 3.1 Podman Sandbox Tool — Pre-built Image (Day 1-2)

**Dockerfile (pre-built during install):**
```dockerfile
# Dockerfile.sandbox
FROM python:3.11-slim
RUN pip install --no-cache-dir numpy pandas matplotlib requests duckduckgo-search \
    beautifulsoup4 lxml pandas openpyxl
WORKDIR /workspace
CMD ["python"]
```

**Build & Push during installation:**
```bash
# In install script / run.py bootstrap
podman build -t ayassek/sandbox:latest -f Dockerfile.sandbox .
```

**Tool:**
```python
# ayassek/tools/builtins/code_tool.py
class CodeExecutionTool(BaseTool):
    def __init__(self, image="ayassek/sandbox:latest", timeout=60):
        self.image = image
        self.timeout = timeout
    
    async def execute(self, code: str, files: dict[str, str] = {}) -> ToolResult:
        # Write code + files to temp dir
        # podman run --rm -v /tmp/xyz:/workspace -w /workspace \
        #   --memory=512m --cpus=1 --pids-limit=50 --network=none \
        #   ayassek/sandbox:latest python script.py
        # Capture stdout/stderr, return
```

### 3.2 File System Tools (Day 2)

```python
class ReadFileTool(BaseTool):      # Read file in workspace/
class WriteFileTool(BaseTool):     # Write file in workspace/
class ListFilesTool(BaseTool):     # List directory in workspace/
class GlobTool(BaseTool):          # Glob pattern in workspace/
class GrepTool(BaseTool):          # Search content in workspace/
```
- Restricted to `workspace/` directory (configurable)
- Path traversal protection (resolve, check prefix)

### 3.3 Browser Automation Tool (Day 3)

Reference: `REPOSTOINSPIRE/browser-use-main`
```python
# ayassek/tools/builtins/browser_tool.py
class BrowserTool(BaseTool):
    """Playwright-based browser automation."""
    async def execute(self, action: str, **kwargs) -> ToolResult:
        # actions: navigate, click, type, scroll, screenshot, extract_text, wait_for_selector
        # Returns: text, screenshot (base64), or structured data
```
- Headless Chromium via Playwright
- Session persistence (cookies, localStorage) per task
- Screenshot → base64 for vision analysis (Phase 2)

### 3.4 Enhanced Planner — LangGraph-inspired (Day 4)

```python
# ayassek/reasoning/planner_v2.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class PlanStep:
    id: str
    action: str
    description: str
    tool: str | None
    args: dict
    depends_on: list[str]
    expected_output: str
    fallback: str | None

@dataclass
class Plan:
    goal: str
    steps: list[PlanStep]
    checkpoints: list[int]  # step indices requiring human approval

class AdvancedPlanner:
    def __init__(self, provider_manager, tool_registry):
        self.llm = provider_manager.get_active_provider()
        self.tools = tool_registry
    
    async def plan(self, goal: str, context: dict) -> Plan:
        # 1. Decompose goal into subtasks via LLM
        # 2. Assign tools to each subtask
        # 3. Create execution graph with dependencies
        # 4. Identify checkpoints for human-in-the-loop
        # 5. Return Plan
    
    async def execute(self, plan: Plan, session_id: str) -> ExecutionResult:
        # Execute with reflection loop, retry on failure
        # Persist state to GraphDB for resume
```

### 3.5 Reflection Loop Deepening (Day 4-5)

```python
# ayassek/reasoning/reflection.py
@dataclass
class Reflection:
    decision: Literal["continue", "retry", "replan", "ask_user", "done"]
    reasoning: str
    suggested_changes: dict | None

class ReflectionLoop:
    async def reflect(self, goal: str, actions: list[Action], results: list[Result]) -> Reflection:
        # Critique: Did actions achieve goal? What went wrong?
        # Suggest: Retry with different tool? Decompose further? Ask user?
        # Return structured decision
```

### 3.6 Agent Workflows (Day 5)

- YAML-defined workflows: `research → summarize → store_in_brain`
- Trigger: manual, scheduled, webhook, chat command (`/workflow research "topic"`)
- Workflow engine with checkpointing and persistence

---

## Phase 2: Multimodal Vision (Week 6)

### 2.1 Vision Provider (Day 1)

```python
# ayassek/providers/vision.py
class VisionProvider:
    """Wrapper for qwen3-vl:8b via Ollama."""
    
    async def analyze(self, images: list[str], prompt: str) -> str:
        # images: base64 data URLs or file paths
        # Uses Ollama chat with images in messages
        # Supports multiple images per request
```

### 2.2 Vision Tool (Day 1-2)

```python
# ayassek/tools/builtins/vision_tool.py
class VisionAnalyzeTool(BaseTool):
    async def execute(self, images: list[str], prompt: str = "Describe this image in detail") -> ToolResult:
        provider = get_vision_provider()
        result = await provider.analyze(images, prompt)
        return ToolResult(success=True, output=result)
```

### 2.3 Document Vision Ingestion — Pipeline Híbrido (Day 2)

```python
# ayassek/memory/ingest.py (extend)
async def ingest_pdf_hybrid(self, file_path: str, **kwargs):
    # 1. Check if PDF has text layer (PyMuPDF/pdfplumber)
    # 2. If YES (digital): Use marker for structured extraction
    # 3. If NO (scanned): pdf2image → Qwen3-VL per page
    # 4. Combine results → RAG + Second Brain (category: references)
```

**Dependencies:** `marker-pdf`, `pdf2image`, `pymupdf`, `poppler-utils` (system)

### 2.4 Frontend Vision (Day 3)

- Image upload in chat (drag-drop, paste, camera capture)
- Preview thumbnails with remove button
- Send with message → vision tool called automatically
- Display vision analysis in tool result expandable

### 2.5 Camera/Stream (Day 4)

- Webcam capture button in chat input
- Optional: RTSP stream URL input for robotics prep

---

## Reference Patterns from REPOSTOINSPIRE

| Feature | Reference Repo | Key Pattern |
|---------|---------------|-------------|
| Knowledge Graph | `graphify-8`, `graphiti-main` | Entity extraction, temporal edges, Graphiti ontology |
| Agent Memory | `mem0-main`, `letta-main`, `zep-main` | Fact extraction, versioning, semantic search |
| Browser Automation | `browser-use-main` | Playwright + LLM action loop |
| Code Execution | `openinterpreter-main`, `OpenHands-main` | Sandboxed containers, file persistence |
| Voice STT | `HAL9000`, `live-vlm-webui` | faster-whisper, Web Audio API recording |
| Voice TTS | `kokoro-main` | KPipeline, voice packs, streaming |
| VLM WebUI | `live-vlm-webui` | WebSocket streaming, webcam capture |
| Agent Orchestration | `langgraph-main` | StateGraph, checkpointers, interrupts |
| RAG | `llama_index-main` | Ingestion pipeline, retrievers, rerankers |

---

## Database Strategy (Confirmed)

- **SQLite** → GraphDB (sessions, neurons, synapses, KV) — KEEP
- **LanceDB** → Vector embeddings (RAG, Second Brain index) — KEEP
- **KuzuDB** → Evaluate ONLY if real need for property graph queries

---

## Milestone Schedule

| Week | Phase | Key Deliverable |
|------|-------|-----------------|
| 1 | 5.1-5.3 | Bugs fixed, React scaffold, Second Brain panel |
| 2 | 5.4-5.7 | RAG panel (hybrid pipeline), Neural Graph (React Flow), Chat polish, Build |
| 3 | 4.1-4.5 | STT/TTS services, Voice tools, Frontend voice UI, Integration |
| 4 | 3.1-3.3 | Podman sandbox (pre-built), File tools, Browser tool |
| 5 | 3.4-3.6 | Advanced planner, Reflection loop, Workflows |
| 6 | 2.1-2.5 | Vision provider, Vision tool, Hybrid PDF ingestion, Frontend, Camera |

---

## Configuration Additions Needed

### defaults.yaml additions:

```yaml
# Voice configuration
voice:
  stt:
    enabled: true
    model: "base"  # tiny, base, small, medium
    device: "auto"
    compute_type: "int8"
    language: "pt"
  tts:
    enabled: true
    engine: "kokoro"  # kokoro, piper
    lang_code: "a"  # a=EN, p=PT-BR
    voice: "af_heart"
    sample_rate: 24000

# Sandbox configuration
sandbox:
  enabled: true
  image: "ayassek/sandbox:latest"
  timeout: 60
  memory_limit: "512m"
  cpu_limit: "1"
  network: "none"

# Vision configuration
vision:
  enabled: true
  provider: "ollama"
  model: "qwen3-vl:8b"
  max_images_per_request: 5

# PDF ingestion pipeline
pdf_ingestion:
  digital_pipeline: "marker"      # marker for digital PDFs
  scanned_pipeline: "qwen3-vl"    # pdf2image + qwen3-vl for scanned
  auto_detect: true
  dpi: 200                        # for pdf2image
```

### settings.py additions:

- `VoiceConfig`, `SandboxConfig`, `VisionConfig`, `PDFIngestionConfig` classes
- Add to `Settings` class
- Update `load_settings()` to parse new sections

---

## Questions for Confirmation

1. **React UI**: Confirm `@xyflow/react` for graphs, Tailwind for styling?
2. **Voice models**: Default STT `base` (74MB) OK? Or prefer `small` (244MB) for accuracy?
3. **Sandbox image**: Build `ayassek/sandbox:latest` during `run.py` bootstrap? Or separate install script?
4. **Marker**: Add `marker-pdf` to requirements? (Heavy deps: torch, transformers, layoutlm)
5. **WebSocket audio**: Binary frames or base64 JSON? (Binary more efficient)
6. **Workflow triggers**: Start with manual (`/workflow`) only, add cron/webhook later?

---

**Ready to begin Phase 5.1 (Bug Fixes) upon confirmation.**