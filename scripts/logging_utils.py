"""Shared logging setup for all ETF Terminal scripts."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging and return the etf_terminal logger."""
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    return logging.getLogger("etf_terminal")
