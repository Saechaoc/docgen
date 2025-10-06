"""Logging utilities for docgen commands."""

from __future__ import annotations

import logging
from pathlib import Path

_LOGGER_NAME = "docgen"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a module-scoped logger under the docgen hierarchy."""
    full_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    return logging.getLogger(full_name)


def configure_logging(
    *, verbose: bool = False, log_file: Path | None = None
) -> logging.Logger:
    """Configure root logger for docgen with console output and optional file sink."""
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    # Reset handlers to avoid duplicate output when CLI is invoked multiple times.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter("[docgen] %(levelname)s %(message)s"))
    logger.addHandler(stream_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(file_handler)

    return logger


__all__ = ["configure_logging", "get_logger"]
