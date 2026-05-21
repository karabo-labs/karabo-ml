"""Structured logging setup for kb CLI."""

import sys
import logging
from pathlib import Path


def setup_logger(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure kb logger with console + optional file handler.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file (~/.kb/kb.log)

    Returns:
        Configured logger instance.
    """
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger("kb")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler (stderr — stdout is for output)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path))
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def get_logger() -> logging.Logger:
    """Get the kb logger (auto-creates if not set up)."""
    logger = logging.getLogger("kb")
    if not logger.handlers:
        return setup_logger()
    return logger
