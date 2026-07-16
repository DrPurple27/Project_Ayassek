#!/usr/bin/env bash
# Ayassek dependency installer — run once before starting the app.
#
# Usage:
#   ./scripts/install.sh          # core deps only
#   ./scripts/install.sh --voice  # core + voice (kokoro/misaki)
#   ./scripts/install.sh --marker # core + marker-pdf/surya-ocr (--no-deps)
#   ./scripts/install.sh --all    # core + voice + marker
#
# Exit codes: 0 success, 1 failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PY="${PYTHON:-python3}"

cd "$PROJECT_DIR"

# --- core deps --------------------------------------------------------------
echo "[install] Core dependencies..."
"$PY" -m pip install -e . || {
    echo "[install] ERROR: core install failed." >&2
    exit 1
}

# --- optional deps -----------------------------------------------------------
INSTALL_VOICE=false
INSTALL_MARKER=false
for arg in "$@"; do
    case "$arg" in
        --voice) INSTALL_VOICE=true ;;
        --marker) INSTALL_MARKER=true ;;
        --all)    INSTALL_VOICE=true; INSTALL_MARKER=true ;;
    esac
done

if $INSTALL_VOICE; then
    echo "[install] Voice dependencies (kokoro/misaki)..."
    EXTRA_FLAGS=""
    # kokoro/misaki declare py<3.13 upper bound — on Python 3.14+ bypass it (pure-Python).
    if "$PY" -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)"; then
        EXTRA_FLAGS="--ignore-requires-python"
    fi
    "$PY" -m pip install ".[voice]" $EXTRA_FLAGS || \
        echo "[install] WARN: voice deps failed — TTS/STT unavailable." >&2
fi

if $INSTALL_MARKER; then
    echo "[install] Marker deps (surya-ocr/marker-pdf) with --no-deps..."
    "$PY" -m pip install --no-deps surya-ocr>=0.17.0 marker-pdf>=1.0.0 || \
        echo "[install] WARN: marker deps failed — PDF ingestion limited." >&2
fi

# --- playwright --------------------------------------------------------------
echo "[install] Playwright Chromium..."
"$PY" -m playwright install --with-deps chromium || \
    echo "[install] WARN: playwright install failed." >&2

# --- HuggingFace models (pre-download so first request doesn't hang) ----------
echo "[install] Pre-downloading embedding + reranker models..."
"$PY" scripts/preload_models.py || \
    echo "[install] WARN: HF model preload failed — models will download on first request." >&2

# --- Ollama models (optional, requires ollama running) ------------------------
if command -v ollama &>/dev/null; then
    echo "[install] Pulling Ollama models..."
    ollama pull qwen2.5:1.5b 2>&1 || echo "[install] WARN: ollama pull qwen2.5:1.5b failed." >&2
else
    echo "[install] Ollama not found — skipping model pull."
fi

# --- frontend ---------------------------------------------------------------
echo "[install] Frontend (npm ci + build)..."
if [ -d "frontend" ]; then
    (cd frontend && npm ci && npm run build) || \
        echo "[install] WARN: frontend build failed — serving stale dist/." >&2
else
    echo "[install] No frontend/ directory — skipping frontend build."
fi

echo "[install] Done."
echo "  Start with:      python run.py"
echo "  Or (re)build:     scripts/install.sh --voice --marker"
