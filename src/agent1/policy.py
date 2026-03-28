from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from agent1.config import Settings


@dataclass
class EffectiveToolPolicy:
    profile: str
    allow_tools: set[str]
    deny_tools: set[str]
    deny_permissions: set[str]


PROFILE_PRESETS: dict[str, dict[str, set[str]]] = {
    "full": {
        "allow_tools": set(),
        "deny_tools": set(),
        "deny_permissions": set(),
    },
    "safe": {
        "allow_tools": set(),
        "deny_tools": {"safe_shell", "send_email", "create_calendar_event", "write_file"},
        "deny_permissions": {"shell_exec"},
    },
    "messaging": {
        "allow_tools": set(),
        "deny_tools": {
            "safe_shell",
            "write_file",
            "send_email",
            "create_calendar_event",
            "read_recent_emails",
            "read_file",
            "list_files",
        },
        "deny_permissions": {"shell_exec", "python_exec"},
    },
}


def _split_csv(value: str) -> set[str]:
    return {part.strip() for part in (value or "").split(",") if part.strip()}


class ToolPolicyManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store_path: Path = settings.tool_policy_store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.store_path.exists():
            self._save({"users": {}})

    def _load(self) -> dict:
        raw = self.store_path.read_text(encoding="utf-8").strip() if self.store_path.exists() else ""
        if not raw:
            return {"users": {}}
        return json.loads(raw)

    def _save(self, data: dict) -> None:
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_profiles(self) -> list[str]:
        return sorted(PROFILE_PRESETS.keys())

    def _user_row(self, user_id: str) -> dict:
        data = self._load()
        return data.get("users", {}).get(str(user_id), {})

    def get_effective_policy(self, user_id: str) -> EffectiveToolPolicy:
        user = self._user_row(user_id)
        profile_name = str(user.get("profile") or self.settings.default_tool_profile or "full").strip().lower()
        preset = PROFILE_PRESETS.get(profile_name, PROFILE_PRESETS["full"])

        allow_tools = set(preset["allow_tools"])
        deny_tools = set(preset["deny_tools"])
        deny_permissions = set(preset["deny_permissions"])

        allow_tools |= _split_csv(self.settings.tool_policy_global_allow)
        deny_tools |= _split_csv(self.settings.tool_policy_global_deny)
        deny_permissions |= _split_csv(self.settings.tool_policy_global_deny_permissions)

        allow_tools |= set(user.get("allow_tools", []))
        deny_tools |= set(user.get("deny_tools", []))
        deny_permissions |= set(user.get("deny_permissions", []))

        return EffectiveToolPolicy(
            profile=profile_name,
            allow_tools=allow_tools,
            deny_tools=deny_tools,
            deny_permissions=deny_permissions,
        )

    def set_user_profile(self, user_id: str, profile: str) -> tuple[bool, str]:
        profile = profile.strip().lower()
        if profile not in PROFILE_PRESETS:
            return False, f"Unknown profile `{profile}`. Options: {', '.join(self.list_profiles())}"

        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            row = users.setdefault(str(user_id), {})
            row["profile"] = profile
            row.setdefault("allow_tools", [])
            row.setdefault("deny_tools", [])
            row.setdefault("deny_permissions", [])
            self._save(data)
        return True, f"Tool profile set to `{profile}`."

    def set_user_tool_override(self, user_id: str, mode: str, tool_name: str) -> tuple[bool, str]:
        mode = mode.strip().lower()
        tool_name = tool_name.strip()
        if not tool_name:
            return False, "Tool name cannot be empty."
        if mode not in {"allow", "deny", "clear"}:
            return False, "Mode must be one of: allow, deny, clear."

        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            row = users.setdefault(str(user_id), {})
            allow_tools = set(row.get("allow_tools", []))
            deny_tools = set(row.get("deny_tools", []))

            if mode == "allow":
                allow_tools.add(tool_name)
                deny_tools.discard(tool_name)
            elif mode == "deny":
                deny_tools.add(tool_name)
                allow_tools.discard(tool_name)
            else:
                allow_tools.discard(tool_name)
                deny_tools.discard(tool_name)

            row["allow_tools"] = sorted(allow_tools)
            row["deny_tools"] = sorted(deny_tools)
            row.setdefault("deny_permissions", [])
            self._save(data)

        if mode == "clear":
            return True, f"Cleared tool override for `{tool_name}`."
        return True, f"Set tool override: `{tool_name}` -> `{mode}`."

    def set_user_permission_override(self, user_id: str, mode: str, permission: str) -> tuple[bool, str]:
        mode = mode.strip().lower()
        permission = permission.strip().lower()
        if not permission:
            return False, "Permission cannot be empty."
        if mode not in {"deny", "allow", "clear"}:
            return False, "Mode must be one of: allow, deny, clear."

        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            row = users.setdefault(str(user_id), {})
            deny_permissions = set(row.get("deny_permissions", []))

            if mode == "deny":
                deny_permissions.add(permission)
            else:
                deny_permissions.discard(permission)

            row.setdefault("allow_tools", [])
            row.setdefault("deny_tools", [])
            row["deny_permissions"] = sorted(deny_permissions)
            self._save(data)

        if mode == "deny":
            return True, f"Permission `{permission}` denied for this user."
        if mode == "allow":
            return True, f"Permission `{permission}` allow override applied (removed deny)."
        return True, f"Permission `{permission}` override cleared."

    def clear_user_overrides(self, user_id: str) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            row = users.setdefault(str(user_id), {})
            row["allow_tools"] = []
            row["deny_tools"] = []
            row["deny_permissions"] = []
            self._save(data)
        return True, "Cleared custom tool and permission overrides."

    def is_tool_allowed(self, user_id: str, tool_name: str) -> tuple[bool, str]:
        policy = self.get_effective_policy(user_id)
        if tool_name in policy.deny_tools and tool_name not in policy.allow_tools:
            return False, f"Tool `{tool_name}` blocked by `{policy.profile}` profile."
        return True, ""

    def are_skill_permissions_allowed(self, user_id: str, permissions: list[str]) -> tuple[bool, str]:
        policy = self.get_effective_policy(user_id)
        blocked = [item for item in permissions if item in policy.deny_permissions]
        if blocked:
            return False, f"Skill blocked by `{policy.profile}` profile due to permissions: {', '.join(blocked)}."
        return True, ""
