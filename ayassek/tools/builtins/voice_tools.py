from __future__ import annotations

from ayassek.memory.voice.stt import STTService
from ayassek.memory.voice.tts import TTSService
from ayassek.tools.base import BaseTool, ToolResult, ToolSpec


class VoiceSpeakTool(BaseTool):
    name: str = "voice_speak"
    description: str = "Synthesize text to speech audio"

    def __init__(self, tts_service: TTSService | None = None):
        self._tts = tts_service or TTSService()

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "text": {
                    "type": "string",
                    "description": "Text to speak aloud",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice to use (e.g., af_heart, af_bella, am_michael)",
                    "default": "af_heart",
                },
                "speed": {
                    "type": "number",
                    "description": "Speech speed multiplier (0.5-2.0)",
                    "default": 1.0,
                },
            },
            required=["text"],
        )

    async def execute(self, text: str, voice: str = "af_heart", speed: float = 1.0) -> ToolResult:
        if not self._tts.is_available():
            return ToolResult(success=False, output="TTS not available. Check configuration.")

        try:
            audio_bytes = self._tts.synthesize(text, voice=voice, speed=speed)
            if not audio_bytes:
                return ToolResult(success=False, output="TTS synthesis returned empty audio.")

            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            return ToolResult(
                success=True,
                output=f"Audio generated ({len(audio_bytes)} bytes). Send audio_b64 to frontend.",
                data={
                    "audio_b64": audio_b64,
                    "format": "wav",
                    "sample_rate": 24000,
                    "text": text,
                    "voice": voice,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=f"TTS synthesis failed: {e}")


class VoiceTranscribeTool(BaseTool):
    name: str = "voice_transcribe"
    description: str = "Transcribe audio to text using speech-to-text"

    def __init__(self, stt_service: STTService | None = None):
        self._stt = stt_service or STTService()

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "audio_b64": {
                    "type": "string",
                    "description": "Base64-encoded WAV audio data",
                },
                "language": {
                    "type": "string",
                    "description": "Language code (e.g., 'en', 'pt'). Auto-detected if omitted.",
                    "default": "",
                },
            },
            required=["audio_b64"],
        )

    async def execute(self, audio_b64: str, language: str = "") -> ToolResult:
        if not self._stt.is_available():
            return ToolResult(success=False, output="STT not available. Check configuration.")

        try:
            import base64
            audio_bytes = base64.b64decode(audio_b64)

            result = self._stt.transcribe(audio_bytes, language=language or None)
            if result.get("error"):
                return ToolResult(success=False, output=f"Transcription failed: {result['error']}")

            return ToolResult(
                success=True,
                output=result.get("text", ""),
                data=result,
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Transcription failed: {e}")
