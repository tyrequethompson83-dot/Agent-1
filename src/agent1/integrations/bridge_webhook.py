from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.interfaces.base import ChatAdapter

logger = logging.getLogger(__name__)


class BridgeWebhookAdapter(ChatAdapter):
    """
    Generic bridge adapter for WhatsApp/iMessage-style integrations.
    External bridge services can POST inbound messages and receive agent replies.
    """

    def __init__(self, settings: Settings, orchestrator: AgentOrchestrator):
        self.settings = settings
        self.orchestrator = orchestrator

    def _is_allowed_channel(self, channel: str) -> bool:
        allowed = self.settings.allowed_bridge_channels
        if not allowed:
            return True
        return channel.lower().strip() in allowed

    def _is_authorized(self, token: str | None) -> bool:
        configured = self.settings.bridge_auth_token.strip()
        if not configured:
            return True
        return str(token or "").strip() == configured

    @staticmethod
    async def _post_reply(reply_url: str, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(reply_url, json=payload)
        except Exception as exc:
            logger.warning("Bridge reply callback failed: %s", exc)

    def run(self) -> None:
        try:
            import uvicorn
            from fastapi import FastAPI, Header, HTTPException
            from pydantic import BaseModel
        except Exception as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError("Bridge adapter requires `fastapi` and `uvicorn` installed.") from exc

        class InboundMessage(BaseModel):
            channel: str
            user_id: str
            text: str
            reply_url: str = ""
            metadata: dict[str, Any] = {}

        app = FastAPI(title="Agent 1 Bridge Adapter", version="1.0.0")

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok", "adapter": "bridge"}

        @app.post("/v1/message")
        async def message(payload: InboundMessage, x_agent1_token: str | None = Header(default=None)) -> dict[str, Any]:
            channel = payload.channel.strip().lower()
            user_id = payload.user_id.strip()
            text = payload.text.strip()
            reply_url = payload.reply_url.strip()

            if not self._is_authorized(x_agent1_token):
                raise HTTPException(status_code=401, detail="Unauthorized bridge token.")
            if not channel:
                raise HTTPException(status_code=400, detail="channel is required.")
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required.")
            if not text:
                raise HTTPException(status_code=400, detail="text is required.")
            if not self._is_allowed_channel(channel):
                raise HTTPException(status_code=403, detail=f"Channel `{channel}` is not allowed.")

            virtual_user_id = f"{channel}:{user_id}"
            reply = await asyncio.to_thread(self.orchestrator.process_message, virtual_user_id, text)
            outbound = {
                "channel": channel,
                "user_id": user_id,
                "reply": reply,
            }
            if reply_url:
                asyncio.create_task(self._post_reply(reply_url, outbound))
            return outbound

        uvicorn.run(
            app,
            host=self.settings.bridge_host,
            port=int(self.settings.bridge_port),
            log_level="info",
        )
