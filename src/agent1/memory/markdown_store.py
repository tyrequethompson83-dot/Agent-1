from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class MarkdownMemoryStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: str) -> Path:
        user_dir = self.base_dir / "users" / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _file(self, user_id: str, filename: str, title: str) -> Path:
        path = self._user_dir(user_id) / filename
        if not path.exists():
            path.write_text(f"# {title}\n\n", encoding="utf-8")
        return path

    def append_chat_turn(self, user_id: str, user_text: str, assistant_text: str) -> None:
        path = self._file(user_id, "chat_history.md", "Chat History")
        entry = (
            f"## {_utc_now()}\n"
            f"**User:** {user_text.strip()}\n\n"
            f"**Agent:** {assistant_text.strip()}\n\n"
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    def add_fact(self, user_id: str, key: str, value: str) -> None:
        path = self._file(user_id, "facts.md", "User Facts")
        line = f"- {_utc_now()} | **{key.strip()}**: {value.strip()}\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def add_note(self, user_id: str, note: str) -> None:
        path = self._file(user_id, "notes.md", "Notes")
        line = f"- {_utc_now()} | {note.strip()}\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def add_task(self, user_id: str, task: str, due_date: str | None = None) -> str:
        path = self._file(user_id, "tasks.md", "Tasks")
        task_id = f"T-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        due_piece = f" | due: {due_date.strip()}" if due_date else ""
        line = f"- [ ] ({task_id}) {task.strip()}{due_piece} | created: {_utc_now()}\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return task_id

    def list_tasks(self, user_id: str, status: str = "open") -> list[dict[str, str]]:
        path = self._file(user_id, "tasks.md", "Tasks")
        pattern = re.compile(r"^- \[(?P<done>[ x])\] \((?P<id>[^)]+)\) (?P<body>.+)$")
        rows: list[dict[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            done = match.group("done") == "x"
            item_status = "done" if done else "open"
            if status != "all" and item_status != status:
                continue
            rows.append(
                {
                    "id": match.group("id"),
                    "status": item_status,
                    "text": match.group("body"),
                }
            )
        return rows

    def complete_task(self, user_id: str, task_id: str) -> bool:
        path = self._file(user_id, "tasks.md", "Tasks")
        lines = path.read_text(encoding="utf-8").splitlines()
        updated = False
        rewritten: list[str] = []
        marker = f"({task_id})"

        for line in lines:
            raw = line
            if not updated and marker in raw and raw.strip().startswith("- [ ]"):
                raw = raw.replace("- [ ]", "- [x]", 1)
                updated = True
            rewritten.append(raw)

        if updated:
            path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        return updated

    def recent_chat(self, user_id: str, max_chars: int = 3000) -> str:
        path = self._file(user_id, "chat_history.md", "Chat History")
        content = path.read_text(encoding="utf-8")
        return content[-max_chars:]

    def recent_facts(self, user_id: str, max_items: int = 20) -> str:
        path = self._file(user_id, "facts.md", "User Facts")
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip().startswith("- ")]
        return "\n".join(lines[-max_items:])

    def recent_notes(self, user_id: str, max_items: int = 20) -> str:
        path = self._file(user_id, "notes.md", "Notes")
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip().startswith("- ")]
        return "\n".join(lines[-max_items:])

    def list_known_user_ids(self) -> list[str]:
        users_root = self.base_dir / "users"
        if not users_root.exists():
            return []
        return sorted([p.name for p in users_root.iterdir() if p.is_dir()])

