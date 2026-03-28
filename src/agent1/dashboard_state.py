from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agent1.config import Settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int = 120) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


@dataclass
class DashboardSession:
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: str
    message_count: int


@dataclass
class DashboardMessage:
    id: str
    role: str
    content: str
    created_at: str
    kind: str = "message"


class DashboardSessionStore:
    def __init__(self, settings: Settings):
        self.root: Path = settings.data_dir / "dashboard"
        self.messages_root: Path = self.root / "messages"
        self.sessions_path: Path = self.root / "sessions.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.messages_root.mkdir(parents=True, exist_ok=True)
        if not self.sessions_path.exists():
            self._save({"sessions": {}})

    @staticmethod
    def _empty_payload() -> dict:
        return {"sessions": {}}

    def _load(self) -> dict:
        if not self.sessions_path.exists():
            return self._empty_payload()
        raw = self.sessions_path.read_text(encoding="utf-8").strip()
        if not raw:
            return self._empty_payload()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._empty_payload()
        sessions = payload.get("sessions")
        if not isinstance(sessions, dict):
            return self._empty_payload()
        return payload

    def _save(self, data: dict) -> None:
        self.sessions_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _message_path(self, session_id: str) -> Path:
        return self.messages_root / f"{session_id}.jsonl"

    @staticmethod
    def _default_title(session_id: str) -> str:
        return f"Session {session_id[:8]}"

    @staticmethod
    def _session_from_row(row: dict) -> DashboardSession:
        return DashboardSession(
            id=str(row.get("id", "")),
            user_id=str(row.get("user_id", "")),
            title=str(row.get("title", "")),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            last_message_preview=str(row.get("last_message_preview", "")),
            message_count=int(row.get("message_count", 0) or 0),
        )

    @staticmethod
    def _message_from_row(row: dict) -> DashboardMessage:
        return DashboardMessage(
            id=str(row.get("id", "")),
            role=str(row.get("role", "assistant")),
            content=str(row.get("content", "")),
            created_at=str(row.get("created_at", "")),
            kind=str(row.get("kind", "message")),
        )

    def _bootstrap_from_known_users(self, known_user_ids: list[str]) -> None:
        payload = self._load()
        sessions = payload.setdefault("sessions", {})
        changed = False
        for user_id in known_user_ids:
            if not str(user_id).startswith("dashboard:"):
                continue
            session_id = str(user_id).split("dashboard:", 1)[1].strip()
            if not session_id or session_id in sessions:
                continue
            now = _utc_now_iso()
            sessions[session_id] = {
                "id": session_id,
                "user_id": str(user_id),
                "title": self._default_title(session_id),
                "created_at": now,
                "updated_at": now,
                "last_message_preview": "",
                "message_count": 0,
            }
            changed = True
        if changed:
            self._save(payload)

    def ensure_default_session(self, known_user_ids: list[str] | None = None) -> DashboardSession:
        if known_user_ids:
            self._bootstrap_from_known_users(known_user_ids)
        rows = self.list_sessions(limit=1)
        if rows:
            return rows[0]
        return self.create_session(title="Main Session")

    def list_sessions(self, limit: int = 100) -> list[DashboardSession]:
        payload = self._load()
        rows = [
            self._session_from_row(row)
            for row in payload.get("sessions", {}).values()
            if isinstance(row, dict)
        ]
        rows.sort(key=lambda item: item.updated_at, reverse=True)
        return rows[:limit]

    def get_session(self, session_id: str) -> DashboardSession | None:
        payload = self._load()
        row = payload.get("sessions", {}).get(session_id)
        if not isinstance(row, dict):
            return None
        return self._session_from_row(row)

    def create_session(self, title: str = "") -> DashboardSession:
        session_id = uuid4().hex[:12]
        now = _utc_now_iso()
        title = title.strip() or self._default_title(session_id)
        row = {
            "id": session_id,
            "user_id": f"dashboard:{session_id}",
            "title": title,
            "created_at": now,
            "updated_at": now,
            "last_message_preview": "",
            "message_count": 0,
        }
        payload = self._load()
        payload.setdefault("sessions", {})[session_id] = row
        self._save(payload)
        message_path = self._message_path(session_id)
        if not message_path.exists():
            message_path.write_text("", encoding="utf-8")
        return self._session_from_row(row)

    def touch_session(
        self,
        session_id: str,
        *,
        title_hint: str = "",
        last_message_preview: str = "",
        message_count: int | None = None,
    ) -> DashboardSession | None:
        payload = self._load()
        row = payload.get("sessions", {}).get(session_id)
        if not isinstance(row, dict):
            return None
        row["updated_at"] = _utc_now_iso()
        if last_message_preview.strip():
            row["last_message_preview"] = _clip(last_message_preview, limit=140)
        if message_count is not None:
            row["message_count"] = int(message_count)
        current_title = str(row.get("title", "")).strip()
        if title_hint.strip() and (not current_title or current_title.startswith("Session ")):
            row["title"] = _clip(title_hint.strip().splitlines()[0], limit=48)
        payload["sessions"][session_id] = row
        self._save(payload)
        return self._session_from_row(row)

    def append_message(self, session_id: str, role: str, content: str, *, kind: str = "message") -> DashboardMessage:
        session = self.get_session(session_id)
        if not session:
            raise KeyError(f"Unknown dashboard session: {session_id}")
        message = DashboardMessage(
            id=f"msg-{uuid4().hex[:12]}",
            role=role.strip() or "assistant",
            content=content,
            created_at=_utc_now_iso(),
            kind=kind,
        )
        path = self._message_path(session_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(message.__dict__, ensure_ascii=True) + "\n")
        count = len(self.list_messages(session_id=session_id, limit=5000))
        self.touch_session(
            session_id,
            title_hint=content if role == "user" else "",
            last_message_preview=content,
            message_count=count,
        )
        return message

    def list_messages(self, session_id: str, limit: int = 200) -> list[DashboardMessage]:
        path = self._message_path(session_id)
        if not path.exists():
            return []
        rows: list[DashboardMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            rows.append(self._message_from_row(parsed))
        return rows[-limit:]
