from __future__ import annotations

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from ayassek.config.settings import settings


def setup_logging() -> logging.Logger:
    root = logging.getLogger("ayassek")
    root.setLevel(getattr(logging, settings.logging.level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path = Path(settings.logging.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ayassek.{name}")