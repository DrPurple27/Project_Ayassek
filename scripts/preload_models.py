#!/usr/bin/env python3
"""Pre-download HuggingFace embedding + reranker models so the first request doesn't hang."""
import os
import sys

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")

MODELS = {
    "embedding": "Qwen/Qwen3-Embedding-0.6B",
    "reranker": "Qwen/Qwen3-Reranker-0.6B",
}


def preload():
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"[preload] Embedding model: {MODELS['embedding']}")
    try:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(MODELS["embedding"], cache_folder=CACHE_DIR)
        print("[preload] Embedding model loaded OK")
    except Exception as e:
        print(f"[preload] WARN: embedding model failed: {e}", file=sys.stderr)

    print(f"[preload] Reranker model: {MODELS['reranker']}")
    try:
        from sentence_transformers import CrossEncoder
        CrossEncoder(MODELS["reranker"], cache_folder=CACHE_DIR)
        print("[preload] Reranker model loaded OK")
    except Exception as e:
        print(f"[preload] WARN: reranker model failed: {e}", file=sys.stderr)

    print("[preload] Done")


if __name__ == "__main__":
    preload()