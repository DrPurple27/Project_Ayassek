from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    USER_MESSAGE = "user.message"
    BRAIN_THINKING = "brain.thinking"
    BRAIN_TOKEN = "brain.token"
    BRAIN_TOOL_CALL = "brain.tool_call"
    BRAIN_TOOL_RESULT = "brain.tool_result"
    BRAIN_RESPONSE = "brain.response"
    BRAIN_ERROR = "brain.error"
    BRAIN_DONE = "brain.done"
    PROVIDER_CHANGED = "provider.changed"
    SYSTEM_STATUS = "system.status"
    SYSTEM_LOGS = "system.logs"
    MEMORY_UPDATED = "memory.updated"
    CONFIG_CHANGED = "config.changed"
    INGEST_STARTED = "ingest.started"
    INGEST_PROGRESS = "ingest.progress"
    INGEST_COMPLETE = "ingest.complete"
    INGEST_FAILED = "ingest.failed"
    VOICE_TRANSCRIBE_START = "voice.transcribe_start"
    VOICE_TRANSCRIBE_RESULT = "voice.transcribe_result"
    VOICE_TTS_CHUNK = "voice.tts_chunk"
    VOICE_TTS_DONE = "voice.tts_done"
    # NRS real-time events
    NRS_REMEMBERED = "nrs.remembered"
    NRS_RECALLED = "nrs.recalled"
    ENTITY_CREATED = "entity.created"
    ENTITY_UPDATED = "entity.updated"
    ENTITY_DELETED = "entity.deleted"
    FACT_ADDED = "fact.added"
    FACT_UPDATED = "fact.updated"
    FACT_DELETED = "fact.deleted"
    NEURON_CREATED = "neuron.created"
    NEURON_UPDATED = "neuron.updated"
    NEURON_DELETED = "neuron.deleted"


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "session_id": self.session_id,
        }