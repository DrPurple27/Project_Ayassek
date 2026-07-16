from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ayassek.core.brain import AyassekBrain
from ayassek.core.bus import AsyncEventBus
from ayassek.core.events import Event, EventType
from ayassek.config.settings import settings
from ayassek.memory.ingest import start_ingestion_worker
from ayassek.memory.manager import MemoryManager
from ayassek.providers.manager import ProviderManager
from ayassek.reasoning.executor import ActionExecutor
from ayassek.reasoning.workflow import WorkflowEngine
from ayassek.tools.registry import ToolRegistry
from ayassek.utils.logging import get_logger

from .routes import chat as chat_routes
from .routes import providers as provider_routes
from .routes import memory as memory_routes
from .routes import config as config_routes
from .routes import system as system_routes
from .routes import rag as rag_routes
from .routes import brain as brain_routes
from .routes import voice as voice_routes
from .routes import workflow as workflow_routes
from ayassek.memory.voice.stt import STTService
from ayassek.memory.voice.tts import TTSService


STATIC_DIR = Path(__file__).parent / "static"


class WebSocketManager:
    def __init__(self, event_bus: AsyncEventBus):
        self._bus = event_bus
        self._clients: dict[str, set[WebSocket]] = {}
        self._logger = get_logger("ws_manager")
        self._bus.subscribe_global(self._broadcast_event)
        self._brain: AyassekBrain | None = None

    def set_brain(self, brain: AyassekBrain):
        self._brain = brain

    async def connect(self, websocket: WebSocket, session_id: str = "default"):
        await websocket.accept()
        if session_id not in self._clients:
            self._clients[session_id] = set()
        self._clients[session_id].add(websocket)
        self._logger.info("WS client connected, session=%s, total=%d", session_id, len(self._clients[session_id]))

    def disconnect(self, websocket: WebSocket, session_id: str | None = None):
        if session_id is not None:
            if session_id in self._clients:
                self._clients[session_id].discard(websocket)
                if not self._clients[session_id]:
                    del self._clients[session_id]
            self._logger.info("WS client disconnected, session=%s", session_id)
        else:
            for sid in list(self._clients.keys()):
                self._clients[sid].discard(websocket)
                if not self._clients[sid]:
                    del self._clients[sid]
            self._logger.info("WS client disconnected from all sessions")

    async def handle_message(self, session_id: str, message: dict):
        """Handle incoming WebSocket message from client."""
        if self._brain is None:
            return
        msg_type = message.get("type")
        if msg_type == "chat":
            content = message.get("message", "")
            images = message.get("images")
            if content.strip() or images:
                await self._brain.process_message(
                    content=content,
                    session_id=session_id,
                    images=images,
                )

    async def _broadcast_event(self, event: Event):
        data = json.dumps(event.to_dict(), default=str)
        session_id = event.session_id or "default"
        targets = self._clients.get(session_id, set()).copy()

        dead: list[WebSocket] = []

        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws, session_id=session_id)

    async def send_bytes(self, data: bytes, session_id: str = "default"):
        targets = self._clients.get(session_id, set()).copy()
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_bytes(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id=session_id)

    async def send_to_all(self, event: Event):
        await self._broadcast_event(event)


def create_app(
    brain: AyassekBrain,
    event_bus: AsyncEventBus,
    provider_manager: ProviderManager,
    memory_manager: MemoryManager,
    tool_registry: ToolRegistry,
    tool_executor: ActionExecutor | None = None,
) -> FastAPI:
    logger = get_logger("web")

    ws_manager = WebSocketManager(event_bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Ayassek web interface started")
        ws_manager.set_brain(brain)
        memory_manager.create_session("default", "Default")
        await provider_manager.refresh_models()
        provider_manager.set_active_provider(settings.defaults.provider)
        await provider_manager.auto_select_model()
        try:
            if brain._nrs and hasattr(brain._nrs, 'check_nrs_model_available'):
                nrs_status = await brain._nrs.check_nrs_model_available()
                if not nrs_status["available"]:
                    logger.warning("NRS model '%s' not found. Install: %s", nrs_status["model"], nrs_status["pull_command"])
                else:
                    logger.info("NRS model '%s' available", nrs_status["model"])
        except Exception:
            logger.warning("NRS model check skipped")
        await event_bus.emit(Event(
            type=EventType.SYSTEM_STATUS,
            data={"status": "started", "message": "Ayassek is ready", "model": provider_manager.get_active_model()},
        ))

        await start_ingestion_worker()
        wf_engine = app.state.workflow_engine
        wf_engine.start_scheduler()

        yield
        logger.info("Ayassek shutting down")
        wf_engine.stop_scheduler()
        await event_bus.emit(Event(
            type=EventType.SYSTEM_STATUS,
            data={"status": "shutdown"},
        ))
        await provider_manager.close_all()

    app = FastAPI(
        title="Ayassek",
        description="Multimodal General Brain Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.brain = brain
    app.state.event_bus = event_bus
    app.state.provider_manager = provider_manager
    app.state.memory_manager = memory_manager
    app.state.tool_registry = tool_registry
    app.state.ws_manager = ws_manager
    app.state.workflow_engine = WorkflowEngine(tool_executor=tool_executor)

    app.include_router(chat_routes.router, prefix="/api")
    app.include_router(provider_routes.router, prefix="/api")
    app.include_router(memory_routes.router, prefix="/api")
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(system_routes.router, prefix="/api")
    app.include_router(rag_routes.router)
    app.include_router(brain_routes.router)
    app.include_router(voice_routes.router)
    app.include_router(workflow_routes.router)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        session_id = websocket.query_params.get("session", "default")
        await ws_manager.connect(websocket, session_id)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    try:
                        import json
                        msg = json.loads(data)
                        await ws_manager.handle_message(session_id, msg)
                    except json.JSONDecodeError:
                        pass
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, session_id)
        except Exception:
            ws_manager.disconnect(websocket, session_id)

    @app.websocket("/ws/{session_id}")
    async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
        await ws_manager.connect(websocket, session_id)
        try:
            while True:
                msg_type = await websocket.receive()
                if msg_type.get("type") == "websocket.receive":
                    data = msg_type.get("text") or msg_type.get("bytes")
                    if data == "ping":
                        await websocket.send_text("pong")
                    else:
                        try:
                            import json
                            msg = json.loads(data)
                            await ws_manager.handle_message(session_id, msg)
                        except json.JSONDecodeError:
                            pass
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, session_id)
        except Exception:
            ws_manager.disconnect(websocket, session_id)

    @app.websocket("/ws/audio/stt")
    async def audio_stt_stream(websocket: WebSocket):
        await websocket.accept()
        stt = STTService()

        async def chunk_generator():
            try:
                while True:
                    data = await websocket.receive()
                    if data.get("type") == "websocket.receive":
                        chunk = data.get("bytes") or data.get("text")
                        if isinstance(chunk, str):
                            if chunk == "done":
                                break
                            continue
                        yield chunk
            except Exception:
                pass

        try:
            async for result in stt.transcribe_streaming(chunk_generator()):
                import json
                await websocket.send_text(json.dumps(result, default=str))
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    @app.websocket("/ws/audio/tts")
    async def audio_tts_stream(websocket: WebSocket):
        await websocket.accept()
        tts = TTSService()

        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                    continue
                try:
                    import json
                    req = json.loads(data)
                    text = req.get("text", "")
                    voice = req.get("voice", "af_heart")
                    speed = req.get("speed", 1.0)
                except Exception:
                    await websocket.send_text(json.dumps({"error": "invalid request"}))
                    continue

                if not text:
                    await websocket.send_text(json.dumps({"error": "empty text"}))
                    continue

                async for audio_chunk in tts.synthesize_stream(text, voice=voice, speed=speed):
                    try:
                        await websocket.send_bytes(audio_chunk)
                    except Exception:
                        break

                await websocket.send_text(json.dumps({"final": True}))
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", response_class=HTMLResponse)
        async def serve_spa(full_path: str):
            if full_path.startswith("api/") or full_path.startswith("ws") or full_path.startswith("static/"):
                return HTMLResponse(status_code=404)
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                return index_path.read_text(encoding="utf-8")
            return "<h1>Ayassek</h1><p>Static files not built properly.</p>"

        @app.get("/", response_class=HTMLResponse)
        async def index():
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                return index_path.read_text(encoding="utf-8")
            return "<h1>Ayassek</h1><p>Static files not built. Run frontend build.</p>"

    return app