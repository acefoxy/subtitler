from __future__ import annotations

import logging


def setup_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("subtitler")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
