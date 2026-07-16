#!/usr/bin/env python3
"""
Ayassek — Multimodal General Brain Agent
Single entry point: python run.py
"""

import subprocess
import sys
from pathlib import Path


def _build_frontend():
    static_dir = Path(__file__).parent / "ayassek" / "interfaces" / "web" / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return
    frontend_dir = Path(__file__).parent / "frontend"
    if not frontend_dir.exists():
        return
    print("[build] Frontend static files not found. Building...")
    try:
        subprocess.check_call(
            ["npx", "vite", "build"],
            cwd=str(frontend_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[build] Frontend built successfully.")
    except Exception as e:
        print(f"[build] Frontend build failed: {e}")


def _build_sandbox():
    df = Path(__file__).parent / "Dockerfile.sandbox"
    if not df.exists():
        return
    try:
        result = subprocess.run(
            ["podman", "images", "-q", "ayassek/sandbox:latest"],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            return
        print("[build] Building sandbox image (first run)...")
        subprocess.check_call(
            ["podman", "build", "-t", "ayassek/sandbox:latest", "-f", "Dockerfile.sandbox", "."],
            cwd=str(Path(__file__).parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[build] Sandbox image built.")
    except Exception as e:
        print(f"[build] Sandbox build skipped: {e}")


def _validate_deps():
    missing = []
    critical = ["lancedb", "pyarrow", "chromadb", "sentence_transformers", "transformers"]
    for mod in critical:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"[error] Critical dependencies missing: {', '.join(missing)}")
        print(f"[error] Run: ./scripts/install.sh")
        sys.exit(1)
    voice_optional = {
        "faster_whisper": "faster_whisper",
        "kokoro": "kokoro",
        "misaki": "misaki",
        "soundfile": "soundfile",
        "silero_vad": "silero_vad",
    }
    voice_missing = []
    for label, mod in voice_optional.items():
        try:
            __import__(mod)
        except ImportError:
            voice_missing.append(label)
    if voice_missing:
        print(f"[warn] Voice features unavailable — missing: {', '.join(voice_missing)}")


def _ensure_dirs():
    from ayassek.config.settings import settings
    dirs = [
        settings.storage.upload_dir,
        settings.storage.data_dir,
        settings.memory.second_brain.path,
        str(Path(settings.memory.neural.db_path).parent),
        settings.memory.neural.chroma_path,
        settings.memory.rag.vector_db.path,
        str(Path(settings.logging.file).parent),
        "data/models",
        "data/browser_state",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    from ayassek.memory.second_brain import SecondBrain
    SecondBrain()._ensure_structure()


def _prewarm_models():
    import threading

    def _load():
        try:
            from ayassek.memory.embeddings import get_embedding_service
            svc = get_embedding_service()
            svc.embed(["warmup"])
        except Exception:
            pass
        try:
            from ayassek.memory.reranker import get_reranker_service
            svc = get_reranker_service()
            svc._load_model()
        except Exception:
            pass

    t = threading.Thread(target=_load, daemon=True)
    t.start()
    return t


def bootstrap():
    _build_frontend()
    _build_sandbox()

    from ayassek.config.settings import settings
    from ayassek.utils.logging import setup_logging
    from ayassek.core.bus import AsyncEventBus
    from ayassek.core.events import EventType
    from ayassek.core.brain import AyassekBrain
    from ayassek.core.nrs import NRSOrchestrator
    from ayassek.providers.manager import ProviderManager
    from ayassek.memory.manager import MemoryManager
    from ayassek.tools.registry import ToolRegistry
    from ayassek.tools.builtins.system_ import ShellTool, SystemInfoTool
    from ayassek.tools.builtins.web_tools import WebSearchTool
    from ayassek.tools.builtins.memory_tools import RememberTool, RecallTool, RAGQueryTool, BrainSearchTool
    from ayassek.tools.builtins.voice_tools import VoiceSpeakTool, VoiceTranscribeTool
    from ayassek.tools.builtins.code_tool import CodeExecutionTool
    from ayassek.tools.builtins.file_tools import FileReadTool, FileWriteTool, FileListTool, FileGlobTool, FileGrepTool
    from ayassek.tools.builtins.browser_tool import BrowserTool

    from ayassek.reasoning.executor import ActionExecutor
    from ayassek.reasoning.planner import AdvancedPlanner
    from ayassek.reasoning.reflection import ReflectionLoop
    from ayassek.interfaces.web.app import create_app

    _validate_deps()
    _ensure_dirs()
    logger = setup_logging()

    logger.info("Pre-warming embedding + reranker models in background...")
    _prewarm_models()

    logger.info("Initializing Ayassek...")

    event_bus = AsyncEventBus()

    provider_manager = ProviderManager()
    memory_manager = MemoryManager(event_bus=event_bus)

    nrs = NRSOrchestrator(provider_manager=provider_manager, memory_manager=memory_manager)

    tool_registry = ToolRegistry()
    tool_registry.register(ShellTool())
    tool_registry.register(SystemInfoTool())
    tool_registry.register(WebSearchTool())
    tool_registry.register(RememberTool(memory_manager))
    tool_registry.register(RecallTool(memory_manager))
    tool_registry.register(RAGQueryTool(memory_manager))
    tool_registry.register(BrainSearchTool(memory_manager))
    tool_registry.register(VoiceSpeakTool())
    tool_registry.register(VoiceTranscribeTool())
    tool_registry.register(CodeExecutionTool())
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(FileListTool())
    tool_registry.register(FileGlobTool())
    tool_registry.register(FileGrepTool())
    tool_registry.register(BrowserTool())

    action_executor = ActionExecutor(tool_registry)
    planner = AdvancedPlanner(provider_manager=provider_manager)
    reflection = ReflectionLoop(provider_manager=provider_manager)

    brain = AyassekBrain(
        event_bus=event_bus,
        provider_manager=provider_manager,
        memory_manager=memory_manager,
        tool_executor=action_executor,
        planner=planner,
        reflection=reflection,
        nrs_orchestrator=nrs,
    )

    event_bus.subscribe(EventType.BRAIN_RESPONSE, reflection.record)
    event_bus.subscribe(EventType.BRAIN_TOOL_CALL, reflection.record)
    event_bus.subscribe(EventType.BRAIN_TOOL_RESULT, reflection.record)
    event_bus.subscribe(EventType.BRAIN_ERROR, reflection.record)
    event_bus.subscribe(EventType.USER_MESSAGE, reflection.record)

    app = create_app(
        brain=brain,
        event_bus=event_bus,
        provider_manager=provider_manager,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        tool_executor=action_executor,
    )

    host = settings.server.host
    port = settings.server.port

    logger.info("=" * 60)
    logger.info("  AYASSEK — Multimodal General Brain Agent")
    logger.info("  v1.0.0")
    logger.info("=" * 60)
    logger.info("  Local:   http://localhost:%d", port)
    logger.info("  Network: http://0.0.0.0:%d", port)
    logger.info("  Provider: %s / %s", settings.defaults.provider, settings.defaults.model)
    logger.info("=" * 60)

    return app, host, port


def main():
    import uvicorn
    app, host, port = bootstrap()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()