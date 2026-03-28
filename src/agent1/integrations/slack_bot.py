from __future__ import annotations

import logging
import re

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.interfaces.base import ChatAdapter

logger = logging.getLogger(__name__)


class SlackBotAdapter(ChatAdapter):
    def __init__(self, settings: Settings, orchestrator: AgentOrchestrator):
        self.settings = settings
        self.orchestrator = orchestrator

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 3000) -> list[str]:
        text = text or ""
        if len(text) <= chunk_size:
            return [text]
        out: list[str] = []
        start = 0
        while start < len(text):
            out.append(text[start : start + chunk_size])
            start += chunk_size
        return out

    @staticmethod
    def _strip_mentions(text: str) -> str:
        value = text or ""
        value = re.sub(r"<@[A-Z0-9]+>", "", value)
        return value.strip()

    def _is_allowed(self, user_id: str) -> bool:
        allowed = self.settings.allowed_slack_user_ids
        if not allowed:
            return True
        return str(user_id) in allowed

    def _handle_command(self, user_id: str, text: str) -> str | None:
        text = (text or "").strip()
        if text == "/help":
            return (
                "Slack Commands:\n"
                "/help\n"
                "/doctor\n"
                "/plugins\n"
                "/policy\n"
                "/usage\n"
                "Any other message runs the agent."
            )
        if text == "/doctor":
            return self.orchestrator.doctor_report()
        if text == "/plugins":
            rows = self.orchestrator.list_plugins()
            if not rows:
                return "No plugins installed."
            return "Installed plugins:\n" + "\n".join(
                [
                    f"- {row['name']} [{row['source_type']}] enabled={row['enabled']} "
                    f"pin={row['pin_ref']} skills={row['skills']}"
                    for row in rows
                ]
            )
        if text == "/policy":
            status = self.orchestrator.get_tool_policy_status(user_id)
            return (
                "Tool Policy\n"
                f"- Profile: {status['profile']}\n"
                f"- Allowed tools: {status['allow_tools']}\n"
                f"- Denied tools: {status['deny_tools']}\n"
                f"- Denied permissions: {status['deny_permissions']}"
            )
        if text == "/usage":
            return self.orchestrator.usage_report(user_id)
        return None

    def _respond(self, user_id: str, text: str, say) -> None:
        command_reply = self._handle_command(user_id=user_id, text=text)
        if command_reply is not None:
            for chunk in self._chunk_text(command_reply):
                say(chunk)
            return

        try:
            reply = self.orchestrator.process_message(user_id=user_id, user_input=text)
        except Exception as exc:
            logger.exception("Slack agent processing failed")
            say(f"Agent error: {exc}")
            return
        for chunk in self._chunk_text(reply):
            say(chunk)

    def run(self) -> None:
        if not self.settings.slack_bot_token.strip():
            raise ValueError("SLACK_BOT_TOKEN is required for Slack mode.")
        if not self.settings.slack_app_token.strip():
            raise ValueError("SLACK_APP_TOKEN is required for Slack mode.")

        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler
        except Exception as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError("Slack adapter requires `slack_bolt` installed.") from exc

        app = App(token=self.settings.slack_bot_token)

        @app.event("app_mention")
        def handle_mention(body, say) -> None:
            event = body.get("event", {}) if isinstance(body, dict) else {}
            user_id = str(event.get("user", "")).strip()
            if not user_id or not self._is_allowed(user_id):
                return
            text = self._strip_mentions(str(event.get("text", "")))
            if not text:
                return
            self._respond(user_id=user_id, text=text, say=say)

        @app.event("message")
        def handle_dm(body, say) -> None:
            event = body.get("event", {}) if isinstance(body, dict) else {}
            if event.get("subtype"):
                return
            if str(event.get("channel_type", "")) != "im":
                return
            user_id = str(event.get("user", "")).strip()
            text = str(event.get("text", "")).strip()
            if not user_id or not text or not self._is_allowed(user_id):
                return
            self._respond(user_id=user_id, text=text, say=say)

        handler = SocketModeHandler(app, self.settings.slack_app_token)
        handler.start()
