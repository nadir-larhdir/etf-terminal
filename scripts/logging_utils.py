from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    return logging.getLogger("etf_terminal")
