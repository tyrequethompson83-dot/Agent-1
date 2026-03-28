from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings

logger = logging.getLogger(__name__)


class ProactiveScheduler:
    def __init__(
        self,
        settings: Settings,
        orchestrator: AgentOrchestrator,
        send_message: Callable[[int, str], Awaitable[None]],
    ):
        self.settings = settings
        self.orchestrator = orchestrator
        self.send_message = send_message
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self.subscribers_store = settings.subscribers_store_path
        self.subscribers_store.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.subscribers_store.exists():
            self._save_subscribers({})
        self._running = False

    def _load_subscribers(self) -> dict[str, int]:
        with self._lock:
            raw = self.subscribers_store.read_text(encoding="utf-8").strip() if self.subscribers_store.exists() else ""
            if not raw:
                return {}
            rows = json.loads(raw)
            return {str(k): int(v) for k, v in rows.items()}

    def _save_subscribers(self, data: dict[str, int]) -> None:
        with self._lock:
            self.subscribers_store.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register_subscriber(self, user_id: str, chat_id: int) -> None:
        user_id = str(user_id)
        rows = self._load_subscribers()
        if rows.get(user_id) == int(chat_id):
            return
        rows[user_id] = int(chat_id)
        self._save_subscribers(rows)

    async def _morning_briefing_job(self) -> None:
        subscribers = self._load_subscribers()
        if not subscribers and self.settings.telegram_default_chat_id:
            subscribers = {"default": int(self.settings.telegram_default_chat_id)}
        if not subscribers:
            return

        for user_id, chat_id in subscribers.items():
            try:
                briefing = await asyncio.to_thread(self.orchestrator.generate_morning_briefing, user_id)
                await self.send_message(chat_id, f"Morning Briefing\n\n{briefing}")
            except Exception as exc:
                logger.warning("Morning briefing job failed for user=%s: %s", user_id, exc)

    async def _pending_tasks_digest_job(self) -> None:
        subscribers = self._load_subscribers()
        if not subscribers:
            return
        for user_id, chat_id in subscribers.items():
            try:
                tasks = self.orchestrator.memory.list_tasks(user_id, status="open")
                if not tasks:
                    continue
                top = "\n".join([f"- {item['id']} | {item['text']}" for item in tasks[:5]])
                pending = self.orchestrator.get_pending_approvals_summary(user_id)
                text = (
                    "Pending Task Digest\n\n"
                    f"Open tasks ({len(tasks)}):\n{top}\n\n"
                    f"Pending approvals:\n{pending}\n\n"
                    "Reply with 'summarize my tasks' for a deeper plan."
                )
                await self.send_message(chat_id, text)
            except Exception as exc:
                logger.warning("Pending task digest failed for user=%s: %s", user_id, exc)

    def start(self) -> None:
        if not self.settings.proactive_mode_enabled:
            logger.info("Proactive scheduler disabled by config.")
            return
        if self._running:
            return
        self.scheduler.add_job(
            self._morning_briefing_job,
            trigger="cron",
            hour=self.settings.morning_briefing_hour,
            minute=self.settings.morning_briefing_minute,
            id="morning_briefing",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._pending_tasks_digest_job,
            trigger="interval",
            hours=self.settings.pending_task_digest_hours,
            id="pending_tasks_digest",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info("Proactive scheduler started.")

    async def shutdown(self) -> None:
        if not self._running:
            return
        self.scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Proactive scheduler stopped.")

