from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.interfaces.base import ChatAdapter

logger = logging.getLogger(__name__)


class WhatsAppAdapter(ChatAdapter):
    """
    First-class WhatsApp Cloud API adapter.
    Exposes verification and webhook endpoints compatible with Meta Webhooks.
    """

    def __init__(self, settings: Settings, orchestrator: AgentOrchestrator):
        self.settings = settings
        self.orchestrator = orchestrator

    @staticmethod
    def _chunk_text(text: str, size: int = 1800) -> list[str]:
        value = text.strip()
        if not value:
            return [""]
        return [value[i : i + size] for i in range(0, len(value), size)]

    def _is_allowed_sender(self, sender: str) -> bool:
        allowed = self.settings.allowed_whatsapp_phone_numbers
        if not allowed:
            return True
        return sender.strip() in allowed

    @staticmethod
    def _extract_text_messages(payload: dict[str, Any]) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for entry in payload.get("entry", []):
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []):
                if not isinstance(change, dict):
                    continue
                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue
                for message in value.get("messages", []):
                    if not isinstance(message, dict):
                        continue
                    message_type = str(message.get("type", "")).strip().lower()
                    sender = str(message.get("from", "")).strip()
                    if not sender:
                        continue
                    if message_type == "text":
                        text = str((message.get("text", {}) or {}).get("body", "")).strip()
                    else:
                        # Keep unsupported types visible to the agent while remaining deterministic.
                        text = f"[whatsapp:{message_type}]"
                    if text:
                        rows.append((sender, text))
        return rows

    async def _send_text_reply(self, to: str, text: str) -> None:
        token = self.settings.whatsapp_access_token.strip()
        phone_number_id = self.settings.whatsapp_phone_number_id.strip()
        api_version = self.settings.whatsapp_api_version.strip() or "v21.0"
        if not token or not phone_number_id:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required.")

        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in self._chunk_text(text):
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": chunk},
                }
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

    async def _handle_inbound_message(self, sender: str, text: str) -> None:
        virtual_user = f"whatsapp:{sender}"
        reply = await asyncio.to_thread(self.orchestrator.process_message, virtual_user, text)
        await self._send_text_reply(to=sender, text=reply)

    def run(self) -> None:
        try:
            import uvicorn
            from fastapi import FastAPI, HTTPException, Query, Request
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("WhatsApp adapter requires `fastapi` and `uvicorn`.") from exc

        verify_token = self.settings.whatsapp_verify_token.strip()
        if not verify_token:
            raise ValueError("WHATSAPP_VERIFY_TOKEN is required for WhatsApp mode.")
        if not self.settings.whatsapp_access_token.strip() or not self.settings.whatsapp_phone_number_id.strip():
            raise ValueError("WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required for WhatsApp mode.")

        app = FastAPI(title="Agent 1 WhatsApp Adapter", version="1.0.0")

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok", "adapter": "whatsapp"}

        @app.get("/webhook")
        async def verify_webhook(
            hub_mode: str = Query(default="", alias="hub.mode"),
            hub_verify_token: str = Query(default="", alias="hub.verify_token"),
            hub_challenge: str = Query(default="", alias="hub.challenge"),
        ) -> Any:
            if hub_mode == "subscribe" and hub_verify_token == verify_token:
                return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
            raise HTTPException(status_code=403, detail="Webhook verification failed.")

        @app.post("/webhook")
        async def receive_webhook(request: Request) -> dict[str, Any]:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid webhook payload.")

            accepted = 0
            ignored = 0
            errors: list[str] = []
            for sender, text in self._extract_text_messages(payload):
                if not self._is_allowed_sender(sender):
                    ignored += 1
                    continue
                if not text.strip():
                    ignored += 1
                    continue
                accepted += 1
                try:
                    await self._handle_inbound_message(sender=sender, text=text)
                except Exception as exc:
                    logger.warning("WhatsApp message handling failed for %s: %s", sender, exc)
                    errors.append(f"{sender}: {exc}")

            return {
                "accepted": accepted,
                "ignored": ignored,
                "errors": errors,
            }

        uvicorn.run(
            app,
            host=self.settings.whatsapp_host,
            port=int(self.settings.whatsapp_port),
            log_level="info",
        )
