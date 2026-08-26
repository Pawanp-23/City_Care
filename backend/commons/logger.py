"""Central, rotating, redacted application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    """Configure logging once; no request data, passwords, or tokens are logged."""
    root = logging.getLogger()
    if root.handlers:
        return

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    rotating_file = RotatingFileHandler(
        log_dir / "citycare.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    rotating_file.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(rotating_file)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

