from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agent1.config import Settings
from agent1.tools.approval import ApprovalManager

logger = logging.getLogger("agent1.tools")


class SafeFileTool:
    def __init__(self, settings: Settings, approvals: ApprovalManager):
        self.settings = settings
        self.approvals = approvals
        self.root = settings.safe_files_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _clip(value: str, limit: int = 6000) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "\n... [truncated]"

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path escapes safe root.")
        return candidate

    def list_files(self, user_id: str, relative_path: str = ".") -> str:
        logger.info("tool=list_files user=%s path=%s", user_id, relative_path)
        try:
            target = self._resolve(relative_path)
        except ValueError as exc:
            return f"Denied: {exc}"

        if not target.exists():
            return "Path not found."
        if not target.is_dir():
            return "Target is not a directory."

        rows = []
        for item in sorted(target.iterdir()):
            label = "[DIR]" if item.is_dir() else "     "
            rows.append(f"{label} {item.name}")
        return "\n".join(rows) if rows else "[empty directory]"

    def read_file(self, user_id: str, relative_path: str) -> str:
        logger.info("tool=read_file user=%s path=%s", user_id, relative_path)
        try:
            target = self._resolve(relative_path)
        except ValueError as exc:
            return f"Denied: {exc}"

        if not target.exists():
            return "File not found."
        if not target.is_file():
            return "Target is not a file."

        content = target.read_text(encoding="utf-8")
        return self._clip(content)

    def write_file(self, user_id: str, relative_path: str, content: str, append: bool = False) -> str:
        logger.info("tool=write_file user=%s path=%s append=%s", user_id, relative_path, append)
        try:
            target = self._resolve(relative_path)
        except ValueError as exc:
            return f"Denied: {exc}"

        payload = {
            "path": str(target.relative_to(self.root)),
            "append": append,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        if not self.settings.auto_approve_risky_actions:
            if not self.approvals.consume_if_approved("file_write", payload):
                approval = self.approvals.request_approval(
                    action_type="file_write",
                    payload=payload,
                    requested_by=user_id,
                    reason="File write operation",
                )
                if approval.status == "denied":
                    return (
                        "DENIED: File write rejected by approval policy.\n"
                        f"Request id: `{approval.id}`. Use `/approve {approval.id}` to override."
                    )
                if approval.status == "approved":
                    pass
                else:
                    return (
                        "APPROVAL_REQUIRED: File write blocked pending approval.\n"
                        f"Use `/approve {approval.id}` in Telegram, then re-send the request."
                    )

        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as fh:
            fh.write(content)
        return f"Wrote {len(content)} characters to `{target.relative_to(self.root)}`."
