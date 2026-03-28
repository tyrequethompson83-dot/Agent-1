from __future__ import annotations

import json
from pathlib import Path

from agent1.config import Settings

CURRENT_SCHEMA_VERSION = 1


class MigrationManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_path: Path = settings.schema_state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        raw = self.state_path.read_text(encoding="utf-8").strip() if self.state_path.exists() else ""
        if not raw:
            return {"schema_version": 0}
        return json.loads(raw)

    def _save_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _ensure_json_file(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def migrate(self) -> str:
        state = self._load_state()
        version = int(state.get("schema_version", 0))
        changes: list[str] = []

        if version < 1:
            self._ensure_json_file(self.settings.skills_registry_path, {"entries": {}})
            self._ensure_json_file(self.settings.plugins_registry_path, {"plugins": {}})
            self._ensure_json_file(self.settings.tool_policy_store_path, {"users": {}})
            self._ensure_json_file(self.settings.provider_preferences_path, {"users": {}})
            self._ensure_json_file(self.settings.session_jobs_path, {"jobs": {}})
            version = 1
            changes.append("Applied v1 bootstrap migration (registry/session defaults).")

        state["schema_version"] = version
        self._save_state(state)
        if not changes:
            return f"No migrations needed. Schema is already at v{CURRENT_SCHEMA_VERSION}."
        return "\n".join(changes + [f"Schema now at v{version}."])
