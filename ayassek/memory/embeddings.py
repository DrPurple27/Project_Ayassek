import os
import threading
from typing import Optional

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
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
        self._model_name = settings.memory.rag.embedding.model
        self._device = settings.memory.rag.embedding.device
        self._dimension = settings.memory.rag.embedding.dimension
        self._instruction_aware = settings.memory.rag.embedding.instruction_aware
        self._max_length = settings.memory.rag.embedding.max_length
        self._cache_dir = os.path.join(settings.storage.data_dir, "models")

        os.makedirs(self._cache_dir, exist_ok=True)

    def _get_device(self) -> str:
        if self._device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps"
            except ImportError:
                pass
            return "cpu"
        return self._device

    def _load_model(self):
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers>=2.7.0")
            raise

        device = self._get_device()
        model_kwargs = {}
        tokenizer_kwargs = {"padding_side": "left"}

        if device == "cuda":
            if settings.memory.rag.embedding.use_flash_attention:
                try:
                    model_kwargs["attn_implementation"] = "flash_attention_2"
                    logger.debug("Using flash_attention_2")
                except Exception as e:
                    logger.warning("flash_attention_2 not available, using default attention: %s", e)
            model_kwargs["torch_dtype"] = "float16"

        logger.info(f"Loading embedding model: {self._model_name} on {device}")

        self._model = SentenceTransformer(
            self._model_name,
            cache_folder=self._cache_dir,
            model_kwargs=model_kwargs,
            tokenizer_kwargs=tokenizer_kwargs,
            device=device,
        )

        if self._instruction_aware and "query" not in self._model.prompts:
            self._model.prompts["query"] = settings.memory.rag.embedding.instruction

        actual_dim = self._model.get_sentence_embedding_dimension()
        if actual_dim != self._dimension:
            logger.warning(f"Model dimension ({actual_dim}) differs from config ({self._dimension}). Using model's dimension.")
            self._dimension = actual_dim

        logger.info(f"Embedding model loaded. Dimension: {self._dimension}")

    def embed(
        self,
        texts: list[str],
        instruction: Optional[str] = None,
        prompt_name: Optional[str] = None,
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        self._load_model()

        if not texts:
            return []

        if instruction is not None and self._instruction_aware:
            texts = [f"Instruct: {instruction}\nQuery: {t}" for t in texts]
            prompt_name = None

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
            prompt_name=prompt_name,
        )

        return embeddings.tolist()

    def embed_single(self, text: str, instruction: Optional[str] = None) -> list[float]:
        return self.embed([text], instruction=instruction)[0]

    def similarity(self, emb1: list[float], emb2: list[float]) -> float:
        import numpy as np
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))

    @property
    def dimension(self) -> int:
        if self._model is None:
            self._load_model()
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service