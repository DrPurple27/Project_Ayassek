import os
import threading
from typing import Optional

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class RerankerService:
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
        self._model_name = settings.memory.rag.reranker.model
        self._fallback_name = settings.memory.rag.reranker.fallback
        self._device = settings.memory.rag.reranker.device
        self._max_length = settings.memory.rag.reranker.max_length
        self._use_sigmoid = settings.memory.rag.reranker.use_sigmoid
        self._instruction = settings.memory.rag.reranker.instruction
        self._cache_dir = os.path.join(settings.storage.data_dir, "models")

        self._enabled = settings.memory.rag.reranker.enabled
        self._low_latency_mode = settings.memory.rag.reranker.low_latency_mode

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
            from sentence_transformers import CrossEncoder
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers>=2.7.0")
            raise

        device = self._get_device()
        model_kwargs = {}
        if device == "cuda":
            model_kwargs["torch_dtype"] = "float16"

        try:
            logger.info(f"Loading reranker model: {self._model_name} on {device}")
            self._model = CrossEncoder(
                self._model_name,
                cache_folder=self._cache_dir,
                model_kwargs=model_kwargs,
                device=device,
                max_length=self._max_length,
            )
            logger.info(f"Reranker model loaded: {self._model_name}")
        except Exception as e:
            logger.warning(f"Failed to load primary reranker {self._model_name}: {e}. Trying fallback...")
            try:
                logger.info(f"Loading fallback reranker: {self._fallback_name}")
                self._model = CrossEncoder(
                    self._fallback_name,
                    cache_folder=self._cache_dir,
                    model_kwargs=model_kwargs,
                    device=device,
                    max_length=self._max_length,
                )
                self._model_name = self._fallback_name
                logger.info(f"Fallback reranker loaded: {self._fallback_name}")
            except Exception as e2:
                logger.error(f"Failed to load fallback reranker {self._fallback_name}: {e2}")
                self._enabled = False
                self._model = None

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
        instruction: Optional[str] = None,
    ) -> list[dict]:
        if not self._enabled or self._low_latency_mode or not documents:
            return [{"index": i, "text": doc, "score": 1.0 - (i * 0.01)} for i, doc in enumerate(documents[:top_k])]

        if self._model is None:
            self._load_model()

        if self._model is None:
            logger.warning("No reranker model available, returning original order")
            return [{"index": i, "text": doc, "score": 1.0 - (i * 0.01)} for i, doc in enumerate(documents[:top_k])]

        try:
            instr = instruction or self._instruction
            pairs = [(f"Instruct: {instr}\nQuery: {query}\nDocument: {doc}", "") for doc in documents]

            scores = self._model.predict(pairs, activation_fn="sigmoid" if self._use_sigmoid else None)

            scored_docs = list(zip(range(len(documents)), documents, scores))
            scored_docs.sort(key=lambda x: x[2], reverse=True)

            return [
                {"index": idx, "text": doc, "score": float(score)}
                for idx, doc, score in scored_docs[:top_k]
            ]
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return [{"index": i, "text": doc, "score": 1.0 - (i * 0.01)} for i, doc in enumerate(documents[:top_k])]

    def rerank_with_metadata(
        self,
        query: str,
        documents: list[dict],
        text_key: str = "text",
        top_k: int = 5,
        instruction: Optional[str] = None,
    ) -> list[dict]:
        if not documents:
            return []

        texts = [doc.get(text_key, "") for doc in documents]
        reranked = self.rerank(query, texts, top_k=top_k, instruction=instruction)

        result = []
        for r in reranked:
            idx = r["index"]
            new_doc = documents[idx].copy()
            new_doc["rerank_score"] = r["score"]
            new_doc["rerank_index"] = idx
            result.append(new_doc)

        return result

    @property
    def is_enabled(self) -> bool:
        return self._enabled and not self._low_latency_mode

    @property
    def model_name(self) -> str:
        return self._model_name


_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service