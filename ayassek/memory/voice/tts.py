from __future__ import annotations

import io
import threading
from typing import AsyncIterator

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class TTSService:
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
        self._pipeline = None
        self._model = None
        self._enabled = settings.voice.tts.enabled
        self._last_error = None

    def _load_model(self):
        if self._pipeline is not None:
            return
        try:
            from kokoro import KPipeline, KModel

            lang_code = settings.voice.tts.lang_code
            logger.info("Loading TTS model (lang=%s)...", lang_code)
            self._model = KModel(repo_id="hexgrad/Kokoro-82M")
            self._pipeline = KPipeline(lang_code=lang_code, model=self._model)
            logger.info("TTS model loaded")
        except Exception as e:
            logger.warning("Failed to load TTS model: %s", e)
            self._enabled = False
            self._last_error = str(e)

    def is_available(self) -> bool:
        return self._enabled

    def synthesize(self, text: str, voice: str | None = None, speed: float = 1.0) -> bytes:
        if not self._enabled:
            return b""

        self._load_model()
        if self._pipeline is None:
            return b""

        try:
            import numpy as np
            import soundfile as sf

            voice_name = voice or settings.voice.tts.voice
            sample_rate = settings.voice.tts.sample_rate

            audio_chunks = []
            generator = self._pipeline(text, voice=voice_name, speed=speed)
            for result in generator:
                audio_chunks.append(result.audio.numpy())

            if not audio_chunks:
                return b""

            full_audio = np.concatenate(audio_chunks)
            full_audio_int16 = (full_audio * 32767).astype(np.int16)

            buf = io.BytesIO()
            sf.write(buf, full_audio_int16, sample_rate, format="WAV")
            return buf.getvalue()
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            return b""

    async def synthesize_stream(self, text: str, voice: str | None = None, speed: float = 1.0) -> AsyncIterator[bytes]:
        if not self._enabled:
            return

        self._load_model()
        if self._pipeline is None:
            return

        try:
            import numpy as np
            import soundfile as sf

            voice_name = voice or settings.voice.tts.voice
            sample_rate = settings.voice.tts.sample_rate

            for result in self._pipeline(text, voice=voice_name, speed=speed):
                audio_np = result.audio.numpy()
                audio_int16 = (audio_np * 32767).astype(np.int16)

                buf = io.BytesIO()
                sf.write(buf, audio_int16, sample_rate, format="WAV")
                yield buf.getvalue()
        except Exception as e:
            logger.error("TTS streaming failed: %s", e)
