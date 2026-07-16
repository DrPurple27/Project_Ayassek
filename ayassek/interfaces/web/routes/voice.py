from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ayassek.memory.voice.stt import STTService
from ayassek.memory.voice.tts import TTSService
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/voice")


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0


stt = STTService()
tts = TTSService()


@router.get("/status")
async def voice_status():
    return {
        "stt_enabled": stt.is_available(),
        "tts_enabled": tts.is_available(),
        "stt_model": stt._model.__class__.__name__ if stt._model is not None else "not loaded",
        "tts_engine": "kokoro" if tts.is_available() and tts._pipeline is not None else "not loaded",
        "stt_error": getattr(stt, "_last_error", None),
        "tts_error": getattr(tts, "_last_error", None),
    }


@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    if not tts.is_available():
        raise HTTPException(status_code=503, detail="TTS not available")

    audio_bytes = tts.synthesize(text=req.text, voice=req.voice, speed=req.speed)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")

    return StreamingResponse(
        content=iter([audio_bytes]),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "inline; filename=speech.wav",
            "X-Audio-Length": str(len(audio_bytes)),
        },
    )


@router.post("/transcribe")
async def transcribe(request: Request):
    if not stt.is_available():
        raise HTTPException(status_code=503, detail="STT not available")

    form = await request.form()
    audio_file = form.get("audio")
    language = form.get("language", "")

    if audio_file is None:
        raise HTTPException(status_code=400, detail="No audio file provided")

    audio_bytes = await audio_file.read()
    result = stt.transcribe(audio_bytes, language=language or None)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/settings")
async def voice_settings():
    from ayassek.config.settings import settings
    return {
        "stt": {
            "enabled": settings.voice.stt.enabled,
            "model": settings.voice.stt.model,
            "device": settings.voice.stt.device,
            "compute_type": settings.voice.stt.compute_type,
            "language": settings.voice.stt.language,
        },
        "tts": {
            "enabled": settings.voice.tts.enabled,
            "engine": settings.voice.tts.engine,
            "lang_code": settings.voice.tts.lang_code,
            "voice": settings.voice.tts.voice,
            "sample_rate": settings.voice.tts.sample_rate,
        },
        "stt_available": stt.is_available(),
        "tts_available": tts.is_available(),
    }


@router.patch("/settings")
async def update_voice_settings(request: Request):
    from ayassek.config.settings import settings
    body = await request.json()
    for section_key in ("stt", "tts"):
        if section_key in body:
            for k, v in body[section_key].items():
                cfg = getattr(settings.voice, section_key)
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
    return {"status": "updated"}
