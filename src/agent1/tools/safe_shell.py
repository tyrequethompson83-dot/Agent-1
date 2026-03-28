from __future__ import annotations

import hashlib
import logging
import shlex
import subprocess
from pathlib import Path

from agent1.config import Settings
from agent1.tools.approval import ApprovalManager

logger = logging.getLogger("agent1.tools")


class SafeShellTool:
    BLOCKED_TOKENS = ("&&", "||", ";", "|", "`", "$(", ">", "<", "\n", "\r")
    HARD_BLOCKED_COMMANDS = {"rm", "sudo", "su", "chmod", "chown", "shutdown", "reboot", "mkfs", "dd"}

    def __init__(self, settings: Settings, approvals: ApprovalManager):
        self.settings = settings
        self.approvals = approvals
        self.workdir = settings.safe_shell_workdir
        self.workdir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _clip(value: str, limit: int = 4000) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "\n... [truncated]"

    def _approval_state(self, user_id: str, payload: dict[str, str]) -> tuple[str, str]:
        if self.settings.auto_approve_risky_actions:
            return "allow", ""
        if self.approvals.consume_if_approved("shell", payload):
            return "allow", ""
        approval = self.approvals.request_approval(
            action_type="shell",
            payload=payload,
            requested_by=user_id,
            reason="Shell command execution",
        )
        if approval.status == "approved":
            return "allow", approval.id
        if approval.status == "denied":
            return "denied", approval.id
        return "pending", approval.id

    def run(self, user_id: str, command: str) -> str:
        command = command.strip()
        logger.info("tool=safe_shell user=%s command=%s", user_id, command)

        if any(token in command for token in self.BLOCKED_TOKENS):
            return "Denied: shell chaining, redirection, or subshell tokens are not allowed."

        try:
            args = shlex.split(command, posix=True)
        except ValueError as exc:
            return f"Invalid shell command: {exc}"

        if not args:
            return "No command provided."

        base_cmd = args[0]
        if base_cmd in self.HARD_BLOCKED_COMMANDS:
            return f"Denied: `{base_cmd}` is blocked."
        if base_cmd not in self.settings.safe_shell_allowlist:
            allowlist = ", ".join(sorted(self.settings.safe_shell_allowlist))
            return f"Denied: `{base_cmd}` is not in allowlist. Allowed: {allowlist}"

        payload = {
            "command": command,
            "sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        }
        state, approval_id = self._approval_state(user_id, payload)
        if state == "pending":
            return (
                "APPROVAL_REQUIRED: Shell command blocked pending approval.\n"
                f"Use `/approve {approval_id}` in Telegram, then re-send the request."
            )
        if state == "denied":
            return (
                "DENIED: Shell command rejected by approval policy.\n"
                f"Request id: `{approval_id}`. Use `/approve {approval_id}` to override."
            )

        try:
            completed = subprocess.run(
                args,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=self.settings.safe_shell_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"Command timed out after {self.settings.safe_shell_timeout_seconds}s."
        except Exception as exc:
            return f"Shell execution failed: {exc}"

        stdout = self._clip((completed.stdout or "").strip())
        stderr = self._clip((completed.stderr or "").strip())
        if completed.returncode == 0:
            return f"Command succeeded (code 0).\nSTDOUT:\n{stdout or '[empty]'}"
        return (
            f"Command failed (code {completed.returncode}).\n"
            f"STDOUT:\n{stdout or '[empty]'}\n\n"
            f"STDERR:\n{stderr or '[empty]'}"
        )
