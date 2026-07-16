from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class ProviderConfig(BaseSettings):
    base_url: str = ""
    api_key: str = ""


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 2727
    debug: bool = False


class DefaultsConfig(BaseSettings):
    provider: str = "ollama"
    model: str = "qwen3-vl:8b"
    fallback_model: str = "qwen2.5:1.5b"


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    file: str = "data/logs/ayassek.log"
    max_bytes: int = 10485760
    backup_count: int = 3


class ShortTermConfig(BaseSettings):
    max_messages: int = 50


class NeuralMemoryConfig(BaseSettings):
    db_path: str = "data/neural_memory.db"
    chroma_path: str = "data/chroma"
    auto_connect_threshold: float = 0.75
    default_node_x_range: tuple = (100, 600)
    default_node_y_range: tuple = (100, 400)


# New RAG configuration classes
class EmbeddingConfig(BaseSettings):
    provider: str = "local"
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    dimension: int = 1024
    instruction: str = "Given a web search query, retrieve relevant passages that answer the query"
    batch_size: int = 32
    device: str = "auto"
    use_flash_attention: bool = False
    instruction_aware: bool = True
    max_length: int = 8192


class ChunkingConfig(BaseSettings):
    strategy: str = "semantic"
    chunk_size: int = 600
    chunk_overlap: int = 80
    min_chunk_size: int = 100
    max_chunk_size: int = 1000
    separators: list[str] = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", "]


class VectorDBIndexConfig(BaseSettings):
    metric: str = "cosine"
    num_partitions: int = 256
    num_sub_vectors: int = 128


class VectorDBConfig(BaseSettings):
    provider: str = "lancedb"
    path: str = "data/lancedb"
    table_name: str = "ayassek_rag"
    index: VectorDBIndexConfig = VectorDBIndexConfig()


class RetrievalConfig(BaseSettings):
    top_k_initial: int = 50
    top_k_final: int = 5
    similarity_threshold: float = 0.3


class RerankerConfig(BaseSettings):
    enabled: bool = True
    provider: str = "local"
    model: str = "Qwen/Qwen3-Reranker-0.6B"
    batch_size: int = 16
    max_length: int = 8192
    use_sigmoid: bool = True
    instruction: str = "Given a web search query, retrieve relevant passages that answer the query"
    fallback: str = "bge-reranker-v2-m3"
    device: str = "auto"
    low_latency_mode: bool = False


class RAGConfig(BaseSettings):
    enabled: bool = True
    embedding: EmbeddingConfig = EmbeddingConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    vector_db: VectorDBConfig = VectorDBConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    reranker: RerankerConfig = RerankerConfig()


class AutoSummarizeConfig(BaseSettings):
    enabled: bool = True
    interval_messages: int = 20
    model: str = "qwen2.5:1.5b"
    temperature: float = 0.3


class FactExtractionConfig(BaseSettings):
    enabled: bool = True
    model: str = "qwen2.5:1.5b"
    temperature: float = 0.3


class LinkSuggestionsConfig(BaseSettings):
    enabled: bool = True
    similarity_threshold: float = 0.75
    max_suggestions: int = 5


class SecondBrainConfig(BaseSettings):
    enabled: bool = True
    path: str = "data/second_brain"
    categories: list[str] = ["projects", "people", "concepts", "meetings", "references", "tasks"]
    auto_summarize: AutoSummarizeConfig = AutoSummarizeConfig()
    fact_extraction: FactExtractionConfig = FactExtractionConfig()
    link_suggestions: LinkSuggestionsConfig = LinkSuggestionsConfig()


class ContradictionDetectionConfig(BaseSettings):
    enabled: bool = True
    threshold: float = 0.7


class BeliefTrackingConfig(BaseSettings):
    enabled: bool = True
    max_versions: int = 10


class EpistemicReasoningConfig(BaseSettings):
    enabled: bool = True


class AutoSummarizeNRSConfig(BaseSettings):
    enabled: bool = True
    interval_minutes: int = 30


class NRSConfig(BaseSettings):
    model: str = "qwen2.5:1.5b"
    temperature: float = 0.3
    provider_order: list[str] = ["ollama", "vllm", "openai", "nim"]
    contradiction_detection: ContradictionDetectionConfig = ContradictionDetectionConfig()
    belief_tracking: BeliefTrackingConfig = BeliefTrackingConfig()
    epistemic_reasoning: EpistemicReasoningConfig = EpistemicReasoningConfig()
    auto_summarize: AutoSummarizeNRSConfig = AutoSummarizeNRSConfig()


class MemoryConfig(BaseSettings):
    short_term: ShortTermConfig = ShortTermConfig()
    neural: NeuralMemoryConfig = NeuralMemoryConfig()
    rag: RAGConfig = RAGConfig()
    second_brain: SecondBrainConfig = SecondBrainConfig()


class VoiceSTTConfig(BaseSettings):
    enabled: bool = True
    model: str = "base"
    device: str = "auto"
    compute_type: str = "int8"
    language: str = "pt"


class VoiceTTSConfig(BaseSettings):
    enabled: bool = True
    engine: str = "kokoro"
    lang_code: str = "a"
    voice: str = "af_heart"
    sample_rate: int = 24000


class VoiceConfig(BaseSettings):
    stt: VoiceSTTConfig = VoiceSTTConfig()
    tts: VoiceTTSConfig = VoiceTTSConfig()


class SandboxConfig(BaseSettings):
    enabled: bool = True
    image: str = "ayassek/sandbox:latest"
    timeout: int = 60
    memory_limit: str = "512m"
    cpu_limit: str = "1"
    network: str = "none"


class StorageConfig(BaseSettings):
    upload_dir: str = "data/uploads"
    data_dir: str = "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AYASSEK_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    server: ServerConfig = ServerConfig()
    defaults: DefaultsConfig = DefaultsConfig()
    providers: dict[str, ProviderConfig] = {
        "openai": ProviderConfig(base_url="https://api.openai.com/v1"),
        "nim": ProviderConfig(base_url="https://ai.api.nvidia.com/v1"),
        "ollama": ProviderConfig(base_url="http://localhost:11434"),
        "vllm": ProviderConfig(base_url="http://localhost:8000/v1"),
    }
    logging: LoggingConfig = LoggingConfig()
    memory: MemoryConfig = MemoryConfig()
    storage: StorageConfig = StorageConfig()
    nrs: NRSConfig = NRSConfig()
    voice: VoiceConfig = VoiceConfig()
    sandbox: SandboxConfig = SandboxConfig()
    debug: bool = False

    # Manual env overrides for providers
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    NIM_API_KEY: str = ""
    NIM_BASE_URL: str = "https://ai.api.nvidia.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_API_KEY: str = ""


def load_settings() -> Settings:
    settings = Settings()

    defaults_path = Path(__file__).parent / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            raw = yaml.safe_load(f)
            if raw:
                if "server" in raw:
                    for k, v in raw["server"].items():
                        setattr(settings.server, k, v)
                if "defaults" in raw:
                    for k, v in raw["defaults"].items():
                        setattr(settings.defaults, k, v)
                if "logging" in raw:
                    for k, v in raw["logging"].items():
                        setattr(settings.logging, k, v)
                if "memory" in raw:
                    if "short_term" in raw["memory"]:
                        for k, v in raw["memory"]["short_term"].items():
                            setattr(settings.memory.short_term, k, v)
                    if "neural" in raw["memory"]:
                        for k, v in raw["memory"]["neural"].items():
                            setattr(settings.memory.neural, k, v)
                    if "rag" in raw["memory"]:
                        rag_raw = raw["memory"]["rag"]
                        if "embedding" in rag_raw:
                            for k, v in rag_raw["embedding"].items():
                                setattr(settings.memory.rag.embedding, k, v)
                        if "chunking" in rag_raw:
                            for k, v in rag_raw["chunking"].items():
                                setattr(settings.memory.rag.chunking, k, v)
                        if "vector_db" in rag_raw:
                            for k, v in rag_raw["vector_db"].items():
                                if k == "index" and isinstance(v, dict):
                                    for ik, iv in v.items():
                                        setattr(settings.memory.rag.vector_db.index, ik, iv)
                                else:
                                    setattr(settings.memory.rag.vector_db, k, v)
                        if "retrieval" in rag_raw:
                            for k, v in rag_raw["retrieval"].items():
                                setattr(settings.memory.rag.retrieval, k, v)
                        if "reranker" in rag_raw:
                            for k, v in rag_raw["reranker"].items():
                                setattr(settings.memory.rag.reranker, k, v)
                        if "enabled" in rag_raw:
                            settings.memory.rag.enabled = rag_raw["enabled"]
                    if "second_brain" in raw["memory"]:
                        sb_raw = raw["memory"]["second_brain"]
                        if "path" in sb_raw:
                            settings.memory.second_brain.path = sb_raw["path"]
                        if "enabled" in sb_raw:
                            settings.memory.second_brain.enabled = sb_raw["enabled"]
                        if "categories" in sb_raw:
                            settings.memory.second_brain.categories = sb_raw["categories"]
                        if "auto_summarize" in sb_raw:
                            for k, v in sb_raw["auto_summarize"].items():
                                setattr(settings.memory.second_brain.auto_summarize, k, v)
                        if "fact_extraction" in sb_raw:
                            for k, v in sb_raw["fact_extraction"].items():
                                setattr(settings.memory.second_brain.fact_extraction, k, v)
                        if "link_suggestions" in sb_raw:
                            for k, v in sb_raw["link_suggestions"].items():
                                setattr(settings.memory.second_brain.link_suggestions, k, v)
                if "storage" in raw:
                    for k, v in raw["storage"].items():
                        setattr(settings.storage, k, v)
                if "rag" in raw:
                    rag_raw = raw["rag"]
                    if "enabled" in rag_raw:
                        settings.memory.rag.enabled = rag_raw["enabled"]
                    if "embedding" in rag_raw:
                        for k, v in rag_raw["embedding"].items():
                            setattr(settings.memory.rag.embedding, k, v)
                    if "chunking" in rag_raw:
                        for k, v in rag_raw["chunking"].items():
                            setattr(settings.memory.rag.chunking, k, v)
                    if "vector_db" in rag_raw:
                        for k, v in rag_raw["vector_db"].items():
                            if k == "index" and isinstance(v, dict):
                                for ik, iv in v.items():
                                    setattr(settings.memory.rag.vector_db.index, ik, iv)
                            else:
                                setattr(settings.memory.rag.vector_db, k, v)
                    if "retrieval" in rag_raw:
                        for k, v in rag_raw["retrieval"].items():
                            setattr(settings.memory.rag.retrieval, k, v)
                    if "reranker" in rag_raw:
                        for k, v in rag_raw["reranker"].items():
                            setattr(settings.memory.rag.reranker, k, v)
                if "second_brain" in raw:
                    sb_raw = raw["second_brain"]
                    if "path" in sb_raw:
                        settings.memory.second_brain.path = sb_raw["path"]
                    if "enabled" in sb_raw:
                        settings.memory.second_brain.enabled = sb_raw["enabled"]
                    if "categories" in sb_raw:
                        settings.memory.second_brain.categories = sb_raw["categories"]
                    if "auto_summarize" in sb_raw:
                        for k, v in sb_raw["auto_summarize"].items():
                            setattr(settings.memory.second_brain.auto_summarize, k, v)
                    if "fact_extraction" in sb_raw:
                        for k, v in sb_raw["fact_extraction"].items():
                            setattr(settings.memory.second_brain.fact_extraction, k, v)
                    if "link_suggestions" in sb_raw:
                        for k, v in sb_raw["link_suggestions"].items():
                            setattr(settings.memory.second_brain.link_suggestions, k, v)
                if "voice" in raw:
                    voice_raw = raw["voice"]
                    if "stt" in voice_raw:
                        for k, v in voice_raw["stt"].items():
                            setattr(settings.voice.stt, k, v)
                    if "tts" in voice_raw:
                        for k, v in voice_raw["tts"].items():
                            setattr(settings.voice.tts, k, v)
                if "sandbox" in raw:
                    for k, v in raw["sandbox"].items():
                        setattr(settings.sandbox, k, v)
                if "nrs" in raw:
                    nrs_raw = raw["nrs"]
                    if "model" in nrs_raw:
                        settings.nrs.model = nrs_raw["model"]
                    if "temperature" in nrs_raw:
                        settings.nrs.temperature = nrs_raw["temperature"]
                    if "contradiction_detection" in nrs_raw:
                        for k, v in nrs_raw["contradiction_detection"].items():
                            setattr(settings.nrs.contradiction_detection, k, v)
                    if "belief_tracking" in nrs_raw:
                        for k, v in nrs_raw["belief_tracking"].items():
                            setattr(settings.nrs.belief_tracking, k, v)
                    if "epistemic_reasoning" in nrs_raw:
                        for k, v in nrs_raw["epistemic_reasoning"].items():
                            setattr(settings.nrs.epistemic_reasoning, k, v)
                    if "auto_summarize" in nrs_raw:
                        for k, v in nrs_raw["auto_summarize"].items():
                            setattr(settings.nrs.auto_summarize, k, v)

    env = os.environ
    if env.get("OPENAI_API_KEY"):
        settings.providers["openai"].api_key = env["OPENAI_API_KEY"]
    if env.get("OPENAI_BASE_URL"):
        settings.providers["openai"].base_url = env["OPENAI_BASE_URL"]
    if env.get("NIM_API_KEY"):
        settings.providers["nim"].api_key = env["NIM_API_KEY"]
    if env.get("NIM_BASE_URL"):
        settings.providers["nim"].base_url = env["NIM_BASE_URL"]
    if env.get("OLLAMA_BASE_URL"):
        settings.providers["ollama"].base_url = env["OLLAMA_BASE_URL"]
    if env.get("VLLM_BASE_URL"):
        settings.providers["vllm"].base_url = env["VLLM_BASE_URL"]
    if env.get("VLLM_API_KEY"):
        settings.providers["vllm"].api_key = env["VLLM_API_KEY"]

    return settings


def save_settings(settings_obj: Settings) -> bool:
    """Persist current settings to defaults.yaml."""
    defaults_path = Path(__file__).parent / "defaults.yaml"
    try:
        data = {
            "server": {
                "host": settings_obj.server.host,
                "port": settings_obj.server.port,
                "debug": settings_obj.server.debug,
            },
            "defaults": {
                "provider": settings_obj.defaults.provider,
                "model": settings_obj.defaults.model,
                "fallback_model": settings_obj.defaults.fallback_model,
            },
            "logging": {
                "level": settings_obj.logging.level,
                "file": settings_obj.logging.file,
                "max_bytes": settings_obj.logging.max_bytes,
                "backup_count": settings_obj.logging.backup_count,
            },
            "memory": {
                "short_term": {"max_messages": settings_obj.memory.short_term.max_messages},
                "neural": {
                    "db_path": settings_obj.memory.neural.db_path,
                    "chroma_path": settings_obj.memory.neural.chroma_path,
                    "auto_connect_threshold": settings_obj.memory.neural.auto_connect_threshold,
                },
                "rag": {
                    "enabled": settings_obj.memory.rag.enabled,
                    "embedding": {
                        "provider": settings_obj.memory.rag.embedding.provider,
                        "model": settings_obj.memory.rag.embedding.model,
                        "dimension": settings_obj.memory.rag.embedding.dimension,
                        "device": settings_obj.memory.rag.embedding.device,
                    },
                    "chunking": {
                        "strategy": settings_obj.memory.rag.chunking.strategy,
                        "chunk_size": settings_obj.memory.rag.chunking.chunk_size,
                        "chunk_overlap": settings_obj.memory.rag.chunking.chunk_overlap,
                    },
                    "vector_db": {
                        "provider": settings_obj.memory.rag.vector_db.provider,
                        "path": settings_obj.memory.rag.vector_db.path,
                        "table_name": settings_obj.memory.rag.vector_db.table_name,
                    },
                    "retrieval": {
                        "top_k_initial": settings_obj.memory.rag.retrieval.top_k_initial,
                        "top_k_final": settings_obj.memory.rag.retrieval.top_k_final,
                        "similarity_threshold": settings_obj.memory.rag.retrieval.similarity_threshold,
                    },
                    "reranker": {
                        "enabled": settings_obj.memory.rag.reranker.enabled,
                        "provider": settings_obj.memory.rag.reranker.provider,
                        "model": settings_obj.memory.rag.reranker.model,
                    },
                },
                "second_brain": {
                    "enabled": settings_obj.memory.second_brain.enabled,
                    "path": settings_obj.memory.second_brain.path,
                    "categories": settings_obj.memory.second_brain.categories,
                },
            },
            "storage": {
                "upload_dir": settings_obj.storage.upload_dir,
                "data_dir": settings_obj.storage.data_dir,
            },
            "voice": {
                "stt": {
                    "enabled": settings_obj.voice.stt.enabled,
                    "model": settings_obj.voice.stt.model,
                    "device": settings_obj.voice.stt.device,
                    "compute_type": settings_obj.voice.stt.compute_type,
                    "language": settings_obj.voice.stt.language,
                },
                "tts": {
                    "enabled": settings_obj.voice.tts.enabled,
                    "engine": settings_obj.voice.tts.engine,
                    "lang_code": settings_obj.voice.tts.lang_code,
                    "voice": settings_obj.voice.tts.voice,
                    "sample_rate": settings_obj.voice.tts.sample_rate,
                },
            },
            "nrs": {
                "model": settings_obj.nrs.model,
                "temperature": settings_obj.nrs.temperature,
            },
            "sandbox": {
                "enabled": settings_obj.sandbox.enabled,
                "image": settings_obj.sandbox.image,
                "timeout": settings_obj.sandbox.timeout,
            },
        }
        with open(defaults_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return True
    except Exception:
        return False


settings = load_settings()