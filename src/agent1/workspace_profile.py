from __future__ import annotations

from pathlib import Path

DEFAULT_WORKSPACE_FILES: dict[str, str] = {
    "AGENTS.md": """# AGENTS.md - Workspace Operating Manual

## Session Bootstrap
Before major work:
1. Read `SOUL.md`
2. Read `USER.md`
3. Read `IDENTITY.md`
4. Read `MEMORY.md`
5. Read `HEARTBEAT.md`

Use these files as your continuity layer.

## Safety
- Never exfiltrate secrets.
- Ask before risky external actions.
- Prefer reversible operations.

## Memory
- Keep curated long-term memory in `MEMORY.md`.
- Keep day logs in `memory/YYYY-MM-DD.md`.
""",
    "HEARTBEAT.md": """# HEARTBEAT.md - Proactive Checklist

When heartbeat runs:
- Check pending approvals.
- Check open tasks.
- Check near-term calendar events.
- Send updates only when there is meaningful new info.

If nothing needs attention, respond with `HEARTBEAT_OK`.
""",
    "IDENTITY.md": """# IDENTITY.md

- Agent Name: Agent 1
- Role: High-agency personal AI operator
- Style: practical, concise, action-oriented
- Default Goal: help users turn intent into safe execution
""",
    "MEMORY.md": """# MEMORY.md - Curated Long-Term Memory

Store durable information that should persist across sessions:
- user preferences
- important project context
- significant decisions
- persistent constraints
""",
    "SOUL.md": """# SOUL.md - Core Behavior

Principles:
- Be useful, not verbose.
- Prefer execution over abstraction.
- Be proactive, but respect consent for risky actions.
- Explain tradeoffs when making decisions.
- Keep outputs clear enough for non-experts.
""",
    "TOOLS.md": """# TOOLS.md - Local Tool Notes

Keep environment-specific notes here:
- local paths
- service endpoints
- deployment quirks
- device aliases
""",
    "USER.md": """# USER.md - User Profile

Keep this generic and private by default.

Suggested sections:
- preferred communication style
- main use cases
- timezone
- recurring priorities
""",
}


class WorkspaceProfile:
    CORE_FILES = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md", "HEARTBEAT.md"]

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.memory_path = self.workspace_path / "memory"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self._cached_context = ""
        self._cached_marker = ""

    def ensure_scaffold(self) -> None:
        for filename, template in DEFAULT_WORKSPACE_FILES.items():
            path = self.workspace_path / filename
            if not path.exists():
                path.write_text(template.strip() + "\n", encoding="utf-8")

        (self.workspace_path / "skills").mkdir(parents=True, exist_ok=True)
        (self.workspace_path / "plugins").mkdir(parents=True, exist_ok=True)

        readme_path = self.memory_path / "README.md"
        if not readme_path.exists():
            readme_path.write_text(
                "# Daily Memory\n\nUse `YYYY-MM-DD.md` files for daily logs and short-term context.\n",
                encoding="utf-8",
            )

    def _read_file(self, filename: str, max_chars: int = 1400) -> str:
        path = self.workspace_path / filename
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8").strip()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... [truncated]"
        return content

    def core_context(self) -> str:
        markers: list[str] = []
        for filename in self.CORE_FILES:
            path = self.workspace_path / filename
            if path.exists():
                markers.append(f"{filename}:{path.stat().st_mtime}")
        marker = "|".join(markers)

        if marker == self._cached_marker and self._cached_context:
            return self._cached_context

        sections: list[str] = []
        for filename in self.CORE_FILES:
            content = self._read_file(filename)
            if not content:
                continue
            sections.append(f"[{filename}]\n{content}")

        self._cached_context = "\n\n".join(sections)
        self._cached_marker = marker
        return self._cached_context
