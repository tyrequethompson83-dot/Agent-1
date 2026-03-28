from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import StructuredTool

from agent1.config import Settings
from agent1.policy import ToolPolicyManager
from agent1.usage_meter import UsageMeter

tool_logger = logging.getLogger("agent1.tools")
audit_logger = logging.getLogger("agent1.agentguard")


@dataclass
class SkillDefinition:
    folder_name: str
    tool_name: str
    display_name: str
    description: str
    usage: str
    permissions: list[str]
    runtime_mode: str
    skill_dir: Path
    skill_md_path: Path
    entrypoint: Path


class UniversalSkillLoader:
    """
    Discovers OpenClaw-style skills from workspace/skills and registers them
    as LangChain/LangGraph-compatible tools.
    """

    ENTRYPOINT_PATTERN = re.compile(r"([A-Za-z0-9_\-./\\]+?\.(?:py|sh|ps1|bat|cmd))", re.IGNORECASE)
    HEADING_PATTERN = re.compile(r"^\s{0,3}(#{1,6})\s*(.+?)\s*$")
    FIELD_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?"
        r"(name|description|usage|runtime|required\s*permissions?|permissions?)\s*:\s*(.+?)\s*$",
        re.IGNORECASE,
    )

    def __init__(
        self,
        settings: Settings,
        policy_manager: ToolPolicyManager | None = None,
        usage_meter: UsageMeter | None = None,
    ):
        self.settings = settings
        self.policy_manager = policy_manager
        self.usage_meter = usage_meter
        self.skills_root: Path = settings.skills_root_path
        self.skills_root.mkdir(parents=True, exist_ok=True)
        self.registry_path: Path = settings.skills_registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save_registry({"entries": {}})
        self._snapshot = ""
        self._all_definitions: dict[str, SkillDefinition] = {}
        self._definitions: dict[str, SkillDefinition] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _clip(text: str, limit: int = 8000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... [truncated]"

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9_]+", "_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        return value or "unnamed_skill"

    @staticmethod
    def _normalize_heading(value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _load_registry(self) -> dict:
        raw = self.registry_path.read_text(encoding="utf-8").strip() if self.registry_path.exists() else ""
        if not raw:
            return {"entries": {}}
        return json.loads(raw)

    def _save_registry(self, data: dict) -> None:
        self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _is_skill_enabled(self, folder_name: str) -> bool:
        registry = self._load_registry()
        row = registry.get("entries", {}).get(folder_name, {})
        if not isinstance(row, dict):
            return True
        if "enabled" not in row:
            return True
        return bool(row.get("enabled"))

    def set_skill_enabled(self, folder_name: str, enabled: bool) -> tuple[bool, str]:
        with self._lock:
            registry = self._load_registry()
            entries = registry.setdefault("entries", {})
            row = entries.setdefault(folder_name, {})
            row["enabled"] = bool(enabled)
            self._save_registry(registry)
        self.reindex(force=True)
        state = "enabled" if enabled else "disabled"
        return True, f"Skill `{folder_name}` {state}."

    def list_skill_states(self, refresh: bool = True) -> list[dict[str, str]]:
        if refresh:
            self.refresh_if_needed()
        registry = self._load_registry()
        disabled = {
            name
            for name, row in registry.get("entries", {}).items()
            if isinstance(row, dict) and row.get("enabled") is False
        }
        out: list[dict[str, str]] = []
        for key, definition in sorted(self._all_definitions.items(), key=lambda item: item[1].folder_name.lower()):
            out.append(
                {
                    "tool_name": definition.tool_name,
                    "folder": definition.folder_name,
                    "display_name": definition.display_name,
                    "status": "disabled" if definition.folder_name in disabled else "enabled",
                    "permissions": ",".join(definition.permissions),
                    "runtime_mode": definition.runtime_mode or "[default]",
                }
            )
        return out

    def _extract_sections(self, markdown_text: str) -> tuple[dict[str, str], list[str]]:
        sections: dict[str, str] = {}
        headings: list[str] = []
        current = "__root__"
        buffer: list[str] = []

        for line in markdown_text.splitlines():
            heading_match = self.HEADING_PATTERN.match(line)
            if heading_match:
                sections[current] = "\n".join(buffer).strip()
                buffer = []
                heading_title = self._normalize_heading(heading_match.group(2))
                headings.append(heading_title)
                current = heading_title
                continue
            buffer.append(line)
        sections[current] = "\n".join(buffer).strip()
        return sections, headings

    def _extract_field_map(self, markdown_text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in markdown_text.splitlines():
            match = self.FIELD_PATTERN.match(line)
            if not match:
                continue
            key = self._normalize_heading(match.group(1))
            out[key] = match.group(2).strip()
        return out

    @staticmethod
    def _first_nonempty_line(block: str) -> str:
        for line in block.splitlines():
            cleaned = line.strip().strip("`")
            if cleaned:
                return cleaned
        return ""

    def _pick_section_value(self, sections: dict[str, str], contains: str) -> str:
        contains = self._normalize_heading(contains)
        for key, value in sections.items():
            if contains in key and value.strip():
                return value.strip()
        return ""

    def _extract_permissions(self, field_map: dict[str, str], sections: dict[str, str], usage: str, entrypoint: Path) -> list[str]:
        raw_value = ""
        for key in ("required permissions", "required permission", "permissions", "permission"):
            if key in field_map:
                raw_value = field_map[key]
                break
        if not raw_value:
            raw_value = self._pick_section_value(sections, "permission")

        permissions: list[str] = []
        if raw_value:
            parts = re.split(r"[,;\n]+", raw_value)
            for part in parts:
                token = part.strip("-* ").strip()
                if token:
                    permissions.append(token)

        usage_l = usage.lower()
        if "docker" in usage_l and "docker_exec" not in permissions:
            permissions.append("docker_exec")
        if "http" in usage_l and "network" not in permissions:
            permissions.append("network")
        if entrypoint.suffix.lower() in {".sh", ".ps1", ".bat", ".cmd"} and "shell_exec" not in permissions:
            permissions.append("shell_exec")
        if entrypoint.suffix.lower() == ".py" and "python_exec" not in permissions:
            permissions.append("python_exec")

        if not permissions:
            permissions = ["unspecified"]
        return sorted(set(permissions))

    def _extract_runtime_mode(self, field_map: dict[str, str], sections: dict[str, str]) -> str:
        raw = (field_map.get("runtime") or self._pick_section_value(sections, "runtime") or "").strip().lower()
        if "docker" in raw:
            return "docker"
        if "process" in raw or "local" in raw or "venv" in raw:
            return "process"
        return ""

    def _select_entrypoint(self, skill_dir: Path, usage: str, markdown_text: str) -> Path | None:
        haystack = f"{usage}\n{markdown_text}"
        candidates = self.ENTRYPOINT_PATTERN.findall(haystack)
        for candidate in candidates:
            normalized = candidate.strip().strip("`\"'").replace("\\", "/")
            if normalized.startswith("./"):
                normalized = normalized[2:]
            path = (skill_dir / normalized).resolve()
            if path.exists() and path.is_file() and skill_dir.resolve() in [path, *path.parents]:
                return path

        for filename in ("main.py", "run.py", "skill.py", "main.sh", "run.sh", "main.ps1", "run.ps1", "run.bat"):
            path = skill_dir / filename
            if path.exists() and path.is_file():
                return path.resolve()
        return None

    def _parse_skill_md(self, skill_dir: Path) -> SkillDefinition | None:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        markdown_text = skill_md.read_text(encoding="utf-8", errors="ignore")
        sections, headings = self._extract_sections(markdown_text)
        field_map = self._extract_field_map(markdown_text)

        fallback_title = headings[0] if headings else skill_dir.name
        name_value = (
            field_map.get("name")
            or self._first_nonempty_line(self._pick_section_value(sections, "name"))
            or fallback_title
            or skill_dir.name
        )
        description_value = (
            field_map.get("description")
            or self._pick_section_value(sections, "description")
            or self._pick_section_value(sections, "summary")
            or f"Community skill loaded from {skill_dir.name}."
        )
        usage_value = (
            field_map.get("usage")
            or self._pick_section_value(sections, "usage")
            or self._pick_section_value(sections, "examples")
            or "Pass arguments as plain text or JSON. JSON dict becomes CLI flags."
        )

        entrypoint = self._select_entrypoint(skill_dir, usage_value, markdown_text)
        if not entrypoint:
            tool_logger.warning("Skipping skill '%s': no executable entrypoint found.", skill_dir.name)
            return None

        base_tool_name = f"skill_{self._slugify(name_value)}"
        tool_name = base_tool_name
        suffix = 2
        while tool_name in self._definitions or tool_name in self._all_definitions:
            tool_name = f"{base_tool_name}_{suffix}"
            suffix += 1

        permissions = self._extract_permissions(field_map, sections, usage_value, entrypoint)
        runtime_mode = self._extract_runtime_mode(field_map, sections)
        return SkillDefinition(
            folder_name=skill_dir.name,
            tool_name=tool_name,
            display_name=name_value.strip(),
            description=description_value.strip(),
            usage=usage_value.strip(),
            permissions=permissions,
            runtime_mode=runtime_mode,
            skill_dir=skill_dir.resolve(),
            skill_md_path=skill_md.resolve(),
            entrypoint=entrypoint.resolve(),
        )

    def _args_from_payload(self, raw_payload: str) -> list[str]:
        payload = (raw_payload or "").strip()
        if not payload:
            return []
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            try:
                return shlex.split(payload, posix=True)
            except ValueError:
                return payload.split()

        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if isinstance(parsed, dict):
            args: list[str] = []
            for key, value in parsed.items():
                flag = f"--{str(key).replace('_', '-')}"
                if isinstance(value, bool):
                    if value:
                        args.append(flag)
                    continue
                if value is None:
                    continue
                if isinstance(value, list):
                    for item in value:
                        args.extend([flag, str(item)])
                    continue
                args.extend([flag, str(value)])
            return args
        return [str(parsed)]

    def _args_are_safe(self, args: list[str]) -> bool:
        if not self.settings.skill_block_unsafe_args:
            return True
        for arg in args:
            token = str(arg).strip()
            if not token:
                continue
            normalized = token.replace("\\", "/")
            if normalized.startswith("../") or "/../" in normalized or normalized == "..":
                return False
            if Path(token).is_absolute():
                return False
        return True

    def _python_for_skill(self, skill_dir: Path) -> str:
        if not self.settings.skill_use_venv_if_present:
            return sys.executable

        if os.name == "nt":
            candidate = skill_dir / ".venv" / "Scripts" / "python.exe"
        else:
            candidate = skill_dir / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
        return sys.executable

    def _command_for_entrypoint(self, entrypoint: Path, skill_dir: Path) -> list[str]:
        suffix = entrypoint.suffix.lower()
        if suffix == ".py":
            return [self._python_for_skill(skill_dir), str(entrypoint)]
        if suffix == ".sh":
            return ["bash", str(entrypoint)]
        if suffix == ".ps1":
            return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(entrypoint)]
        if suffix in {".bat", ".cmd"}:
            return [str(entrypoint)]
        return [str(entrypoint)]

    def _docker_command_for_entrypoint(self, definition: SkillDefinition) -> list[str]:
        try:
            relative_entry = definition.entrypoint.relative_to(definition.skill_dir).as_posix()
        except Exception:
            relative_entry = definition.entrypoint.name
        work_entry = f"/work/{relative_entry}"

        suffix = definition.entrypoint.suffix.lower()
        if suffix == ".py":
            inner = ["python", work_entry]
        elif suffix == ".sh":
            inner = ["bash", work_entry]
        elif suffix == ".ps1":
            inner = ["pwsh", "-File", work_entry]
        else:
            inner = [work_entry]

        network_mode = "bridge" if "network" in definition.permissions else "none"
        return [
            "docker",
            "run",
            "--rm",
            "--init",
            "--network",
            network_mode,
            "--pids-limit",
            "128",
            "--cpus",
            str(self.settings.skill_docker_cpus),
            "--memory",
            f"{self.settings.skill_docker_memory_mb}m",
            "-v",
            f"{str(definition.skill_dir)}:/work",
            "-w",
            "/work",
            self.settings.skill_docker_image,
            *inner,
        ]

    def _effective_runtime_mode(self, definition: SkillDefinition) -> str:
        configured = self.settings.skill_runtime_mode.strip().lower()
        if configured in {"process", "docker"}:
            return configured
        if configured == "auto" and definition.runtime_mode in {"process", "docker"}:
            return definition.runtime_mode
        return "process"

    def _build_tool(self, definition: SkillDefinition, user_id: str) -> StructuredTool:
        def run_skill(arguments: str = "") -> str:
            started = time.perf_counter()
            success = True
            if self.policy_manager:
                ok, reason = self.policy_manager.is_tool_allowed(user_id, definition.tool_name)
                if not ok:
                    return f"Denied: {reason}"
                ok_perm, reason_perm = self.policy_manager.are_skill_permissions_allowed(user_id, definition.permissions)
                if not ok_perm:
                    return f"Denied: {reason_perm}"

            args = self._args_from_payload(arguments)
            if not self._args_are_safe(args):
                return "Denied: unsafe skill arguments detected (absolute path or path traversal)."

            runtime_mode = self._effective_runtime_mode(definition)
            base_command = (
                self._docker_command_for_entrypoint(definition)
                if runtime_mode == "docker"
                else self._command_for_entrypoint(definition.entrypoint, definition.skill_dir)
            )
            command = base_command + args
            tool_logger.info(
                "tool=%s skill=%s entrypoint=%s args=%s",
                definition.tool_name,
                definition.display_name,
                definition.entrypoint,
                args,
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(definition.skill_dir),
                    capture_output=True,
                    text=True,
                    timeout=self.settings.skill_exec_timeout_seconds,
                    check=False,
                )
                success = completed.returncode == 0
            except subprocess.TimeoutExpired:
                success = False
                return f"Skill timed out after {self.settings.skill_exec_timeout_seconds}s."
            except Exception as exc:
                success = False
                return f"Skill execution failed: {exc}"
            finally:
                if self.usage_meter:
                    self.usage_meter.record_tool_call(
                        user_id=user_id,
                        tool_name=definition.tool_name,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        success=success,
                        extra={
                            "kind": "dynamic_skill",
                            "runtime_mode": runtime_mode,
                            "skill_name": definition.display_name,
                        },
                    )

            stdout = self._clip((completed.stdout or "").strip())
            stderr = self._clip((completed.stderr or "").strip())
            if completed.returncode == 0:
                return f"Skill succeeded.\nSTDOUT:\n{stdout or '[empty]'}"
            return (
                f"Skill failed with exit code {completed.returncode}.\n"
                f"STDOUT:\n{stdout or '[empty]'}\n\n"
                f"STDERR:\n{stderr or '[empty]'}"
            )

        description = (
            f"{definition.description}\n\n"
            f"Skill name: {definition.display_name}\n"
            f"Usage: {definition.usage}\n"
            "Input format: pass plain text CLI args or JSON "
            "(dict becomes --flag value pairs, list becomes argv list)."
        )
        return StructuredTool.from_function(
            func=run_skill,
            name=definition.tool_name,
            description=description,
        )

    def _build_snapshot(self) -> str:
        tokens: list[str] = []
        if not self.skills_root.exists():
            return ""
        for skill_dir in sorted([p for p in self.skills_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            skill_md = skill_dir / "SKILL.md"
            skill_md_mtime = skill_md.stat().st_mtime if skill_md.exists() else 0.0
            tokens.append(f"{skill_dir.name}:{skill_dir.stat().st_mtime}:{skill_md_mtime}")
        return "|".join(tokens)

    def _audit_registration(self, definition: SkillDefinition) -> None:
        audit_logger.info(
            "action=register_skill skill=%s tool=%s permissions=%s entrypoint=%s",
            definition.display_name,
            definition.tool_name,
            ",".join(definition.permissions),
            definition.entrypoint,
        )

    def reindex(self, force: bool = False) -> int:
        with self._lock:
            snapshot = self._build_snapshot()
            if not force and snapshot == self._snapshot and self._definitions:
                return len(self._definitions)

            self._all_definitions = {}
            self._definitions = {}
            for skill_dir in sorted([p for p in self.skills_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
                definition = self._parse_skill_md(skill_dir)
                if not definition:
                    continue
                self._all_definitions[definition.tool_name] = definition
                if not self._is_skill_enabled(definition.folder_name):
                    continue
                self._definitions[definition.tool_name] = definition
                self._audit_registration(definition)

            self._snapshot = snapshot
            tool_logger.info(
                "UniversalSkillLoader indexed enabled=%s discovered=%s from %s",
                len(self._definitions),
                len(self._all_definitions),
                self.skills_root,
            )
            return len(self._definitions)

    def refresh_if_needed(self) -> int:
        with self._lock:
            current = self._build_snapshot()
            if current != self._snapshot:
                return self.reindex(force=True)
            return len(self._definitions)

    def get_tools(self, user_id: str, refresh: bool = True) -> dict[str, StructuredTool]:
        if refresh:
            self.refresh_if_needed()
        with self._lock:
            return {key: self._build_tool(definition, user_id=user_id) for key, definition in self._definitions.items()}

    def get_tool_names(self, refresh: bool = True) -> list[str]:
        if refresh:
            self.refresh_if_needed()
        with self._lock:
            return sorted(self._definitions.keys())
