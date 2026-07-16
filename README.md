# Ayassek — Multimodal General Brain Agent

Ayassek is a multimodal general brain agent for AI and robotics. It coordinates language, vision, voice, action, memory, reasoning, and tools through a unified central brain.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
./scripts/install.sh          # core deps + frontend build + playwright
./scripts/install.sh --all    # core + voice (kokoro/misaki) + marker-pdf
python run.py
```

Open **http://localhost:2727** in your browser.

Access from any device on the same network using your machine's IP: `http://YOUR_IP:2727`

### Docker (optional)

```bash
docker compose up --build
```

## Providers

Ayassek works with multiple LLM backends:

| Provider | Status | Requirements |
|----------|--------|-------------|
| **Ollama** | Recommended | [Install Ollama](https://ollama.com), `ollama serve` running |
| **OpenAI** | Supported | `OPENAI_API_KEY` in `.env` |
| **vLLM** | Supported | `vllm serve` running locally |
| **NVIDIA NIM** | Supported | `NIM_API_KEY` in `.env` |

Switch providers and models from the web UI dropdown menus — no code edits needed.

### Ollama Setup (Recommended)

```bash
ollama serve              # Start the server
ollama pull qwen3-vl:8b   # Recommended model (vision-capable)
ollama pull qwen2.5:1.5b  # Fallback (lightweight)
```

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

Key settings:

```env
AYASSEK_HOST=0.0.0.0       # Listen on all interfaces
AYASSEK_PORT=2727           # Web UI port
AYASSEK_DEFAULT_PROVIDER=ollama
AYASSEK_DEFAULT_MODEL=qwen3-vl:8b
```

## Features

- **Chat with streaming** — Real-time token-by-token responses via WebSocket
- **4 providers** — OpenAI, Ollama, NVIDIA NIM, vLLM (each with independent API schema)
- **Tool calling** — Web search, shell commands, system info, memory store/recall
- **Memory** — Short-term conversation buffer, long-term RAG vector store, Second Brain knowledge graph
- **NRS** — Neural Recall System: autonomous memory decisions via local LLM
- **Agent loop** — Planning, execution, reflection, replanning
- **Voice** — STT (faster-whisper) + TTS (kokoro/misaki), optional via `./scripts/install.sh --voice`
- **Web UI** — React + Vite + Tailwind + @xyflow/react (dark-mode, ErrorBoundary per panel)
- **WebSocket** — Real-time event stream for tokens, tool calls, system status
- **Network access** — Serves on `0.0.0.0` by default, accessible from any device

## Architecture

```
ayassek/
├── core/            # Brain, Event Bus, NRS Orchestrator
├── config/          # Settings (.env + YAML)
├── providers/       # OpenAI, NIM, Ollama, vLLM
├── memory/          # Short-term, RAG, Second Brain, Neural DB
├── reasoning/       # Planner, Executor, Reflection
├── tools/           # Tool registry + builtins
├── interfaces/
│   └── web/         # FastAPI + static frontend
└── utils/           # Logging
```

## Project Structure

- `run.py` — Single entry point, boots everything
- `ayassek/` — Python backend
- `ayassek/interfaces/web/static/` — Built frontend (Vite output)
- `frontend/` — React + TypeScript + Vite (build with `npm run build`)
- `scripts/install.sh` — Dependency installer + frontend build + playwright
- `pyproject.toml` — Python deps with optional groups (voice, marker, dev)
- `Dockerfile` + `docker-compose.yml` — Container deployment
- `data/` — Runtime data (memory, uploads, logs)

## Portability

Move the entire folder to another PC, recreate the virtual environment, and run. All paths are relative. Data stays inside the project folder.