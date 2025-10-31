from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def get_logger(name: str = "grader", verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            markup=True,
        )
        handler.setLevel(level)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger

