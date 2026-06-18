from __future__ import annotations

import logging
import sys

from .config import LOG_LEVEL, PROJECT_ROOT


def configure_logging() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8", delay=True)
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=LOG_LEVEL, handlers=[stream_handler, file_handler], force=True)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
