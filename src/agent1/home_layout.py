from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent1.workspace_profile import WorkspaceProfile

HOME_DIRS: tuple[str, ...] = (
    "agents",
    "bin",
    "canvas",
    "credentials",
    "cron",
    "devices",
    "identity",
    "telegram",
    "workspace",
)

CONFIG_BACKUPS: tuple[str, ...] = (
    "agent1.json.bak",
    "agent1.json.bak.1",
    "agent1.json.bak.2",
    "agent1.json.bak.3",
    "agent1.json.bak.4",
    "agent1.json.bak.reset",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_if_missing(path: Path, payload: dict) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def scaffold_agent1_home(home_path: Path, workspace_path: Path | None = None) -> dict[str, Path]:
    """
    Create an OpenClaw-style home folder layout for Agent 1.
    This keeps runtime state centralized under ~/.agent1 while preserving
    Agent 1 naming for config snapshots.
    """
    home = home_path.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    for folder in HOME_DIRS:
        (home / folder).mkdir(parents=True, exist_ok=True)

    workspace = (workspace_path or (home / "workspace")).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    profile = WorkspaceProfile(workspace)
    profile.ensure_scaffold()
    (workspace / "skills").mkdir(parents=True, exist_ok=True)
    (workspace / "plugins").mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(parents=True, exist_ok=True)

    config_payload = {
        "meta": {
            "version": 1,
            "createdAt": _utc_now(),
            "lastTouchedAt": _utc_now(),
        },
        "agent": {
            "id": "main",
            "name": "Agent 1",
            "workspace": str(workspace),
        },
        "defaults": {
            "chatAdapter": "telegram",
            "toolProfile": "full",
        },
    }
    config_path = home / "agent1.json"
    _write_json_if_missing(config_path, config_payload)
    for backup in CONFIG_BACKUPS:
        backup_path = home / backup
        if not backup_path.exists():
            backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    _write_json_if_missing(
        home / "node.json",
        {
            "nodeId": "",
            "gateway": {"host": "127.0.0.1", "port": 0},
            "updatedAt": _utc_now(),
        },
    )
    _write_json_if_missing(
        home / "update-check.json",
        {
            "channel": "stable",
            "lastCheckedAt": "",
            "lastNotifiedVersion": "",
        },
    )
    _write_json_if_missing(
        home / "exec-approvals.json",
        {
            "version": 1,
            "protocol": "exec-approvals.v1",
            "socket": {
                "path": "",
                "token": "",
            },
            "tcp": {
                "host": "",
                "port": 0,
            },
            "socketPath": "",
            "authToken": "",
            "host": "",
            "port": 0,
            "permissions": {
                "default": "ask",
                "allow": [],
                "deny": [],
            },
        },
    )

    _write_text_if_missing(
        home / "identity" / "README.md",
        "# identity\n\nStore non-secret identity/profile notes for Agent 1.",
    )
    _write_text_if_missing(
        home / "credentials" / "README.md",
        "# credentials\n\nDo not commit secrets. Use this folder for local runtime credentials if needed.",
    )
    _write_text_if_missing(
        home / "agents" / "README.md",
        "# agents\n\nReserved for future multi-agent runtime state.",
    )
    _write_text_if_missing(
        home / "telegram" / "README.md",
        "# telegram\n\nReserved for Telegram adapter local state.",
    )
    _write_text_if_missing(
        home / "cron" / "README.md",
        "# cron\n\nReserved for scheduled task metadata.",
    )
    _write_text_if_missing(
        home / "canvas" / "README.md",
        "# canvas\n\nReserved for generated visual artifacts.",
    )
    _write_text_if_missing(
        home / "devices" / "README.md",
        "# devices\n\nReserved for device/session bridge state.",
    )
    _write_text_if_missing(
        home / "bin" / "README.md",
        "# bin\n\nOptional helper scripts for local automation.",
    )

    return {"home": home, "workspace": workspace}
