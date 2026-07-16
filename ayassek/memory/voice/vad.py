from __future__ import annotations

import io
import threading
import numpy as np

from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class VADService:
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
        self._enabled = False

    def _load_model(self):
        if self._model is not None:
            return
        try:
            import silero_vad
            self._model = silero_vad.load_silero_vad()
            self._enabled = True
            logger.info("Silero VAD model loaded")
        except Exception as e:
            logger.warning("Failed to load Silero VAD: %s", e)
            self._enabled = False

    def is_available(self) -> bool:
        return self._enabled

    def get_speech_timestamps(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
    ) -> list[dict]:
        """Detect speech segments in audio using Silero VAD."""
        if not self._enabled:
            self._load_model()
        if not self._enabled or self._model is None:
            return [{"start": 0, "end": 0}]

        try:
            import soundfile as sf

            audio_file = io.BytesIO(audio_bytes)
            audio, sr = sf.read(audio_file)

            if sr != 16000:
                import scipy.signal
                target_len = int(len(audio) * 16000 / sr)
                audio = scipy.signal.resample(audio, target_len)

            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            audio_float32 = audio.astype(np.float32)

            return silero_vad.get_speech_timestamps(
                audio_float32,
                self._model,
                threshold=threshold,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
                sampling_rate=16000,
            )
        except Exception as e:
            logger.warning("VAD detection failed: %s", e)
            return [{"start": 0, "end": 0}]

    def is_speech(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        """Quick check if audio chunk contains speech."""
        timestamps = self.get_speech_timestamps(audio_bytes, sample_rate=sample_rate)
        return len(timestamps) > 0


def get_vad_service() -> VADService:
    return VADService()
