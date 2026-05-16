"""统一应用日志：确保 file_tools 等 INFO 能在 uvicorn 终端看到。"""

from __future__ import annotations

import logging


def configure_app_logging(level: int = logging.INFO) -> None:
    for name in ("app", "file_writer"):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(levelname)s [%(name)s] %(message)s"),
            )
            logger.addHandler(handler)
        logger.propagate = True

    root = logging.getLogger()
    if root.level > level:
        root.setLevel(level)


def log_info(message: str, *args: object) -> None:
    """写入 uvicorn 终端（与访问日志同一控制台）。"""
    logging.getLogger("uvicorn.error").info(message, *args)
