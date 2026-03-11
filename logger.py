"""
logger.py
---------
Logging centralizzato per Frame3D Manager.

Configura un logger con:
  - Console handler (DEBUG)
  - File handler rotante (WARNING+) su 'frame3d.log'
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "frame3d"
LOG_FILE = Path(__file__).parent / "frame3d.log"
MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file di log
BACKUP_COUNT = 3


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Restituisce un logger figlio di 'frame3d'.

    Parameters
    ----------
    name : str | None
        Sotto-nome del logger (es. 'frame_tree' → 'frame3d.frame_tree').
        Se None, restituisce il logger root 'frame3d'.
    """
    full = f"{LOG_NAME}.{name}" if name else LOG_NAME
    return logging.getLogger(full)


def _setup_root_logger() -> None:
    """Configura il logger root una sola volta."""
    logger = logging.getLogger(LOG_NAME)
    if logger.handlers:
        return  # già configurato

    logger.setLevel(logging.DEBUG)

    # ── Console ───────────────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(ch)

    # ── File rotante ──────────────────────────────────────────────────
    try:
        fh = RotatingFileHandler(
            str(LOG_FILE), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        ))
        logger.addHandler(fh)
    except OSError:
        logger.warning("Impossibile creare il file di log: %s", LOG_FILE)


# Auto-setup al primo import
_setup_root_logger()
