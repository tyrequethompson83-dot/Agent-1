from __future__ import annotations

import asyncio
import logging

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.interfaces.base import ChatAdapter

logger = logging.getLogger(__name__)


class DiscordBotAdapter(ChatAdapter):
    def __init__(self, settings: Settings, orchestrator: AgentOrchestrator):
        self.settings = settings
        self.orchestrator = orchestrator

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 1800) -> list[str]:
        text = text or ""
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + chunk_size])
            start += chunk_size
        return chunks

    def _is_allowed(self, user_id: str) -> bool:
        allowed = self.settings.allowed_discord_user_ids
        if not allowed:
            return True
        return str(user_id) in allowed

    def run(self) -> None:
        try:
            import discord
        except Exception as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError("Discord adapter requires `discord.py` installed.") from exc

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            logger.info("Discord bot connected as %s", client.user)

        @client.event
        async def on_message(message) -> None:
            if message.author.bot:
                return
            if not self._is_allowed(message.author.id):
                return

            text = (message.content or "").strip()
            if not text:
                return

            user_id = str(message.author.id)
            if text == "/help":
                await message.channel.send(
                    "Commands:\n"
                    "/help\n"
                    "/doctor\n"
                    "/plugins\n"
                    "/policy\n"
                    "Any other message runs the agent."
                )
                return
            if text == "/doctor":
                for chunk in self._chunk_text(self.orchestrator.doctor_report()):
                    await message.channel.send(chunk)
                return
            if text == "/plugins":
                rows = self.orchestrator.list_plugins()
                if not rows:
                    await message.channel.send("No plugins installed.")
                    return
                payload = "Installed plugins:\n" + "\n".join(
                    [
                        f"- {row['name']} [{row['source_type']}] enabled={row['enabled']} "
                        f"pin={row['pin_ref']} skills={row['skills']}"
                        for row in rows
                    ]
                )
                for chunk in self._chunk_text(payload):
                    await message.channel.send(chunk)
                return
            if text == "/policy":
                status = self.orchestrator.get_tool_policy_status(user_id)
                await message.channel.send(
                    "Tool Policy\n"
                    f"- Profile: {status['profile']}\n"
                    f"- Allowed tools: {status['allow_tools']}\n"
                    f"- Denied tools: {status['deny_tools']}\n"
                    f"- Denied permissions: {status['deny_permissions']}"
                )
                return

            async with message.channel.typing():
                try:
                    reply = await asyncio.to_thread(self.orchestrator.process_message, user_id, text)
                except Exception as exc:  # pragma: no cover - runtime behavior
                    logger.exception("Discord agent processing failed")
                    await message.channel.send(f"Agent error: {exc}")
                    return

            for chunk in self._chunk_text(reply):
                await message.channel.send(chunk)

        if not self.settings.discord_bot_token.strip():
            raise ValueError("DISCORD_BOT_TOKEN is required for Discord mode.")
        client.run(self.settings.discord_bot_token)
