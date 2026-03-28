from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from agent1.config import Settings


def configure_logging(settings: Settings) -> None:
    for path in (
        settings.app_log_path.parent,
        settings.tool_log_path.parent,
        settings.agentguard_audit_log_path.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    app_file = RotatingFileHandler(settings.app_log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    app_file.setFormatter(formatter)
    root.addHandler(app_file)

    tool_logger = logging.getLogger("agent1.tools")
    tool_file = RotatingFileHandler(settings.tool_log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    tool_file.setFormatter(formatter)
    tool_logger.addHandler(tool_file)
    tool_logger.setLevel(logging.INFO)
    tool_logger.propagate = False

    guard_logger = logging.getLogger("agent1.agentguard")
    guard_file = RotatingFileHandler(
        settings.agentguard_audit_log_path,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    guard_file.setFormatter(formatter)
    guard_logger.addHandler(guard_file)
    guard_logger.setLevel(logging.INFO)
    guard_logger.propagate = False
