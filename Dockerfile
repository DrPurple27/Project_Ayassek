FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY scripts/install.sh scripts/install.sh
RUN chmod +x scripts/install.sh

COPY ayassek/ ayassek/
COPY run.py ./
COPY frontend/ frontend/
COPY .env.example .env.example

RUN ./scripts/install.sh

EXPOSE 2727

CMD ["python", "run.py"]
