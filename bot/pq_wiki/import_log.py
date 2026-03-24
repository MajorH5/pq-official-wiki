"""Logging for import runs (Docker logs / stderr)."""

from __future__ import annotations

import logging
import os
import sys

_LOG = logging.getLogger("pq_wiki.import")


def configure_import_logging() -> None:
    if _LOG.handlers:
        return
    level_name = os.environ.get("PQ_IMPORT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [pq-wiki] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    _LOG.addHandler(h)
    _LOG.setLevel(level)
    _LOG.propagate = False


def get_import_logger() -> logging.Logger:
    configure_import_logging()
    return _LOG
