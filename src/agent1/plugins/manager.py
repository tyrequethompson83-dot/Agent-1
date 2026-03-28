from __future__ import annotations

import json
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent1.config import Settings


@dataclass
class PluginRecord:
    name: str
    source: str
    source_type: str
    installed_at: str
    pin_ref: str
    enabled: bool
    skill_folders: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PluginManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.plugins_root_path
        self.registry_path = settings.plugins_registry_path
        self.skills_root = settings.skills_root_path
        self.root.mkdir(parents=True, exist_ok=True)
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.registry_path.exists():
            self._save({"plugins": {}})

    def _load(self) -> dict:
        raw = self.registry_path.read_text(encoding="utf-8").strip() if self.registry_path.exists() else ""
        if not raw:
            return {"plugins": {}}
        return json.loads(raw)

    def _save(self, data: dict) -> None:
        self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _is_git_source(source: str) -> bool:
        source_l = source.lower().strip()
        return source_l.startswith("http://") or source_l.startswith("https://") or source_l.endswith(".git")

    @staticmethod
    def _safe_name(raw: str) -> str:
        out = "".join([ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in raw.strip()])
        out = "_".join([part for part in out.split("_") if part])
        return out.lower() or "plugin"

    def _discover_skill_dirs(self, root: Path) -> list[Path]:
        out: list[Path] = []
        if (root / "SKILL.md").exists():
            out.append(root)
        nested = root / "skills"
        if nested.exists() and nested.is_dir():
            for child in nested.iterdir():
                if child.is_dir() and (child / "SKILL.md").exists():
                    out.append(child)
        return out

    def _copy_skill_dir(self, source: Path, folder_name: str) -> str:
        dest = self.skills_root / folder_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        return folder_name

    def _clone_git(self, source: str, plugin_path: Path, ref: str = "") -> None:
        if plugin_path.exists():
            shutil.rmtree(plugin_path)
        if ref.strip():
            command = ["git", "clone", source, str(plugin_path)]
            subprocess.run(
                command,
                check=True,
                timeout=self.settings.plugin_git_timeout_seconds,
                capture_output=True,
                text=True,
            )
            checkout = ["git", "-C", str(plugin_path), "checkout", ref.strip()]
            subprocess.run(
                checkout,
                check=True,
                timeout=self.settings.plugin_git_timeout_seconds,
                capture_output=True,
                text=True,
            )
        else:
            command = ["git", "clone", "--depth", "1", source, str(plugin_path)]
            subprocess.run(
                command,
                check=True,
                timeout=self.settings.plugin_git_timeout_seconds,
                capture_output=True,
                text=True,
            )

    @staticmethod
    def _remove_path(path: Path) -> None:
        if not path.exists():
            return
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)

    def list_plugins(self) -> list[PluginRecord]:
        data = self._load()
        out: list[PluginRecord] = []
        for name, row in sorted(data.get("plugins", {}).items()):
            if not isinstance(row, dict):
                continue
            out.append(
                PluginRecord(
                    name=name,
                    source=str(row.get("source", "")),
                    source_type=str(row.get("source_type", "")),
                    installed_at=str(row.get("installed_at", "")),
                    pin_ref=str(row.get("pin_ref", "")),
                    enabled=bool(row.get("enabled", True)),
                    skill_folders=list(row.get("skill_folders", [])),
                )
            )
        return out

    def install_plugin(self, source: str, name: str = "", ref: str = "") -> tuple[bool, str]:
        source = source.strip()
        if not source:
            return False, "Source is required."

        source_is_git = self._is_git_source(source)
        source_path = Path(source).resolve() if not source_is_git else None
        if not source_is_git and (not source_path or not source_path.exists() or not source_path.is_dir()):
            return False, "Local plugin source path was not found."

        plugin_name = self._safe_name(name or (Path(source).stem if source_is_git else source_path.name))
        plugin_path = self.root / plugin_name

        try:
            if source_is_git:
                self._clone_git(source, plugin_path, ref=ref)
                materialized_root = plugin_path
                source_type = "git"
            else:
                if plugin_path.exists():
                    shutil.rmtree(plugin_path)
                shutil.copytree(source_path, plugin_path)
                materialized_root = plugin_path
                source_type = "local"
        except Exception as exc:
            return False, f"Plugin materialization failed: {exc}"

        skill_dirs = self._discover_skill_dirs(materialized_root)
        if not skill_dirs:
            return False, "Plugin does not expose SKILL.md at root or in skills/*."

        installed_skill_folders: list[str] = []
        for idx, skill_dir in enumerate(skill_dirs, start=1):
            base = self._safe_name(skill_dir.name)
            folder_name = base if len(skill_dirs) == 1 else f"{plugin_name}_{base}_{idx}"
            installed_skill_folders.append(self._copy_skill_dir(skill_dir, folder_name=folder_name))

        with self._lock:
            data = self._load()
            plugins = data.setdefault("plugins", {})
            current_row = plugins.get(plugin_name, {}) if isinstance(plugins.get(plugin_name, {}), dict) else {}
            plugins[plugin_name] = {
                "source": source,
                "source_type": source_type,
                "installed_at": _utc_now(),
                "pin_ref": ref.strip(),
                "enabled": bool(current_row.get("enabled", True)),
                "skill_folders": installed_skill_folders,
            }
            self._save(data)

        return True, f"Installed plugin `{plugin_name}` with skills: {', '.join(installed_skill_folders)}"

    def update_plugin(self, name: str) -> tuple[bool, str]:
        name = self._safe_name(name)
        data = self._load()
        row = data.get("plugins", {}).get(name)
        if not isinstance(row, dict):
            return False, f"Unknown plugin `{name}`."
        source = str(row.get("source", "")).strip()
        pin_ref = str(row.get("pin_ref", "")).strip()
        if not source:
            return False, f"Plugin `{name}` has no source."
        return self.install_plugin(source=source, name=name, ref=pin_ref)

    def set_plugin_pin(self, name: str, ref: str) -> tuple[bool, str]:
        name = self._safe_name(name)
        ref = ref.strip()
        with self._lock:
            data = self._load()
            row = data.get("plugins", {}).get(name)
            if not isinstance(row, dict):
                return False, f"Unknown plugin `{name}`."
            row["pin_ref"] = ref
            self._save(data)
        if ref:
            return True, f"Plugin `{name}` pinned to `{ref}`."
        return True, f"Plugin `{name}` pin cleared."

    def uninstall_plugin(self, name: str) -> tuple[bool, str]:
        name = self._safe_name(name)
        with self._lock:
            data = self._load()
            row = data.get("plugins", {}).get(name)
            if not isinstance(row, dict):
                return False, f"Unknown plugin `{name}`."
            skill_folders = list(row.get("skill_folders", []))

        try:
            self._remove_path(self.root / name)
        except Exception as exc:
            return False, f"Failed removing plugin files for `{name}`: {exc}"

        failed_skills: list[str] = []
        for folder in skill_folders:
            try:
                self._remove_path(self.skills_root / folder)
            except Exception:
                failed_skills.append(folder)

        with self._lock:
            data = self._load()
            plugins = data.setdefault("plugins", {})
            plugins.pop(name, None)
            self._save(data)

        if failed_skills:
            return True, f"Plugin `{name}` removed, but could not remove skills: {', '.join(failed_skills)}"
        return True, f"Plugin `{name}` uninstalled."

    def set_plugin_enabled(self, name: str, enabled: bool) -> tuple[bool, str, list[str]]:
        name = self._safe_name(name)
        with self._lock:
            data = self._load()
            row = data.get("plugins", {}).get(name)
            if not isinstance(row, dict):
                return False, f"Unknown plugin `{name}`.", []
            row["enabled"] = bool(enabled)
            skill_folders = [str(item) for item in row.get("skill_folders", [])]
            self._save(data)
        state = "enabled" if enabled else "disabled"
        return True, f"Plugin `{name}` {state}.", skill_folders
