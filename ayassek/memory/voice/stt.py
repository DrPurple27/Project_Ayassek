from __future__ import annotations

import io
import asyncio
import threading
from typing import AsyncIterator

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class STTService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._model = None
        self._enabled = settings.voice.stt.enabled
        self._last_error = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel

            model_size = settings.voice.stt.model
            device = settings.voice.stt.device
            compute_type = settings.voice.stt.compute_type

            if device == "auto":
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading STT model: %s (device=%s, compute=%s)", model_size, device, compute_type)
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("STT model loaded")
        except Exception as e:
            logger.warning("Failed to load STT model '%s': %s", settings.voice.stt.model, e)
            self._enabled = False
            self._last_error = str(e)

    def is_available(self) -> bool:
        return self._enabled

    def transcribe(self, audio_bytes: bytes, language: str | None = None) -> dict:
        if not self._enabled:
            return {"text": "", "language": "", "segments": [], "error": "STT not available"}

        self._load_model()
        if self._model is None:
            return {"text": "", "language": "", "segments": [], "error": "STT model not loaded"}

        try:
            import numpy as np
            import soundfile as sf

            audio_file = io.BytesIO(audio_bytes)
            audio, sr = sf.read(audio_file)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            lang = language or settings.voice.stt.language or None
            segments, info = self._model.transcribe(audio, language=lang)

            text_parts = []
            segment_list = []
            for seg in segments:
                text_parts.append(seg.text)
                segment_list.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                })

            return {
                "text": " ".join(text_parts).strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": segment_list,
                "duration": len(audio) / sr if sr > 0 else 0,
            }
        except Exception as e:
            logger.error("STT transcription failed: %s", e)
            return {"text": "", "language": "", "segments": [], "error": str(e)}

    def transcribe_file(self, filepath: str, language: str | None = None) -> dict:
        with open(filepath, "rb") as f:
            audio_bytes = f.read()
        return self.transcribe(audio_bytes, language=language)

    async def transcribe_streaming(
        self,
        audio_chunks: AsyncIterator[bytes],
        language: str | None = None,
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        silence_timeout_ms: int = 800,
    ) -> AsyncIterator[dict]:
        """Streaming transcription with VAD-based speech detection.
        Accumulates audio chunks during speech, transcribes on silence.
        Yields dicts with 'text', 'final' keys.
        """
        if not self._enabled:
            yield {"text": "", "final": True, "error": "STT not available"}
            return

        self._load_model()
        if self._model is None:
            yield {"text": "", "final": True, "error": "STT model not loaded"}
            return

        from ayassek.memory.voice.vad import VADService
        vad = VADService()
        vad._load_model()

        buffer = bytearray()
        is_speaking = False
        silence_start = 0.0

        async for chunk in audio_chunks:
            if not chunk:
                continue

            buffer.extend(chunk)

            if not vad.is_available():
                continue

            is_speech = vad.is_speech(bytes(chunk), sample_rate=sample_rate)

            if is_speech:
                if not is_speaking:
                    is_speaking = True
                silence_start = 0.0
            else:
                if is_speaking:
                    if silence_start == 0.0:
                        silence_start = asyncio.get_event_loop().time()
                    elif (asyncio.get_event_loop().time() - silence_start) * 1000 > silence_timeout_ms:
                        intermediate = bytes(buffer)
                        buffer.clear()
                        is_speaking = False
                        silence_start = 0.0

                        if len(intermediate) > 8000:
                            result = self.transcribe(intermediate, language=language)
                            yield {"text": result.get("text", ""), "final": False}

        if buffer:
            result = self.transcribe(bytes(buffer), language=language)
            yield {"text": result.get("text", ""), "final": True}
        else:
            yield {"text": "", "final": True}
