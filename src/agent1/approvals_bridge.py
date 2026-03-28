from __future__ import annotations

import json
import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from agent1.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ExternalApprovalDecision:
    decision: str
    request_id: str
    message: str


@dataclass
class ExternalApprovalsEndpoint:
    transport: str
    token: str
    socket_path: str = ""
    host: str = ""
    port: int = 0


class ExternalApprovalsBridge:
    """
    Optional best-effort bridge to an external approvals daemon over Unix socket.
    Handshake:
      1) hello
      2) auth with token
      3) authorize request
    If daemon/protocol is unavailable, it safely falls back to local approvals.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.external_approvals_enabled)
        self.config_path: Path = settings.external_approvals_config_path
        self.timeout = max(1, int(settings.external_approvals_timeout_seconds))

    def _load_config(self) -> dict[str, Any]:
        if not self.enabled:
            return {}
        if not self.config_path.exists():
            return {}
        try:
            raw = self.config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("External approvals config parse failed: %s", exc)
            return {}

    @staticmethod
    def _normalize_decision(value: str) -> str:
        raw = value.strip().lower()
        if raw in {"allow", "approved", "ok", "accept", "accepted"}:
            return "approved"
        if raw in {"deny", "denied", "reject", "rejected", "blocked"}:
            return "denied"
        if raw in {"pending", "wait"}:
            return "pending"
        return ""

    @staticmethod
    def _parse_tcp_target(raw: str) -> tuple[str, int] | None:
        value = (raw or "").strip()
        if not value:
            return None
        if "://" in value:
            parsed = urlparse(value)
            host = (parsed.hostname or "").strip()
            port = int(parsed.port or 0)
            if host and port > 0:
                return host, port
            return None
        if value.count(":") >= 1:
            host, sep, port_raw = value.rpartition(":")
            if sep and host and port_raw.isdigit():
                port = int(port_raw)
                if port > 0:
                    return host.strip(), port
        return None

    def _load_endpoint(self) -> ExternalApprovalsEndpoint | None:
        cfg = self._load_config()
        if not cfg:
            return None
        socket_cfg = cfg.get("socket", {}) if isinstance(cfg.get("socket"), dict) else {}
        socket_path = str(socket_cfg.get("path", "")).strip()
        token = str(socket_cfg.get("token", "")).strip()

        # Compatibility fallback for alternate OpenClaw-style formats.
        if not socket_path:
            socket_path = str(cfg.get("socketPath", "")).strip()
        if not token:
            token = str(cfg.get("authToken", "")).strip()
        if not socket_path and isinstance(cfg.get("daemon"), dict):
            daemon_cfg = cfg.get("daemon") or {}
            socket_path = str(daemon_cfg.get("socketPath", "")).strip()
            token = token or str(daemon_cfg.get("authToken", "")).strip()

        tcp_host = ""
        tcp_port = 0
        tcp_cfg = cfg.get("tcp", {}) if isinstance(cfg.get("tcp"), dict) else {}
        if isinstance(tcp_cfg, dict):
            tcp_host = str(tcp_cfg.get("host", "")).strip()
            try:
                tcp_port = int(tcp_cfg.get("port", 0) or 0)
            except Exception:
                tcp_port = 0

        if isinstance(cfg.get("daemon"), dict):
            daemon_cfg = cfg.get("daemon") or {}
            if not tcp_host:
                tcp_host = str(daemon_cfg.get("host", "")).strip()
            if tcp_port <= 0:
                try:
                    tcp_port = int(daemon_cfg.get("port", 0) or 0)
                except Exception:
                    tcp_port = 0

        if not tcp_host:
            tcp_host = str(cfg.get("host", "")).strip()
        if tcp_port <= 0:
            try:
                tcp_port = int(cfg.get("port", 0) or 0)
            except Exception:
                tcp_port = 0

        parsed_target = self._parse_tcp_target(socket_path)
        if parsed_target:
            tcp_host, tcp_port = parsed_target
            socket_path = ""

        if tcp_host and tcp_port > 0:
            return ExternalApprovalsEndpoint(transport="tcp", host=tcp_host, port=tcp_port, token=token)

        if socket_path.startswith("unix://"):
            socket_path = socket_path[len("unix://") :]
        socket_path = os.path.expandvars(os.path.expanduser(socket_path))
        if not socket_path:
            return None
        return ExternalApprovalsEndpoint(transport="unix", socket_path=socket_path, token=token)

    @staticmethod
    def _recv_json_line(client: socket.socket) -> dict[str, Any] | None:
        buffer = b""
        while not buffer.endswith(b"\n"):
            chunk = client.recv(4096)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 262_144:
                break
        if not buffer:
            return None
        line = buffer.decode("utf-8", errors="ignore").strip()
        if not line:
            return None
        try:
            data = json.loads(line)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def _send_json_line(client: socket.socket, payload: dict[str, Any]) -> None:
        client.sendall((json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8"))

    def _perform_handshake(self, client: socket.socket, token: str) -> tuple[bool, str]:
        hello_payload = {
            "type": "hello",
            "client": "agent1",
            "protocol": "exec-approvals.v1",
        }
        self._send_json_line(client, hello_payload)
        hello_response = self._recv_json_line(client) or {}

        auth_payload = {
            "type": "auth",
            "token": token,
        }
        # Some daemons may include nonce/challenge in hello response.
        if "nonce" in hello_response:
            auth_payload["nonce"] = hello_response.get("nonce")
        if "challenge" in hello_response:
            auth_payload["challenge"] = hello_response.get("challenge")

        self._send_json_line(client, auth_payload)
        auth_response = self._recv_json_line(client) or {}
        if auth_response.get("ok") is True:
            return True, ""
        auth_type = str(auth_response.get("type", "")).strip().lower()
        if auth_type in {"auth_ok", "authorized"}:
            return True, ""
        message = str(auth_response.get("message", "")).strip() or "auth_failed"
        return False, message

    def _request_authorize(self, client: socket.socket, request_payload: dict[str, Any]) -> dict[str, Any] | None:
        self._send_json_line(client, request_payload)
        return self._recv_json_line(client)

    def _socket_request(self, endpoint: ExternalApprovalsEndpoint, payload: dict[str, Any]) -> dict[str, Any] | None:
        if endpoint.transport == "tcp":
            try:
                with socket.create_connection((endpoint.host, int(endpoint.port)), timeout=self.timeout) as client:
                    client.settimeout(self.timeout)
                    ok, _reason = self._perform_handshake(client, endpoint.token)
                    if not ok:
                        return None
                    return self._request_authorize(client, payload)
            except Exception as exc:
                logger.debug("External approvals TCP request failed: %s", exc)
                return None

        if os.name == "nt" and not hasattr(socket, "AF_UNIX"):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout)
                client.connect(endpoint.socket_path)
                ok, _reason = self._perform_handshake(client, endpoint.token)
                if not ok:
                    return None
                return self._request_authorize(client, payload)
        except Exception as exc:
            logger.debug("External approvals socket request failed: %s", exc)
            return None

    def request_decision(
        self,
        action_type: str,
        payload: dict[str, Any],
        requested_by: str,
        reason: str,
    ) -> ExternalApprovalDecision | None:
        endpoint = self._load_endpoint()
        if not endpoint:
            return None

        request_id = f"ext-{uuid4().hex[:12]}"
        req = {
            "type": "authorize",
            "id": request_id,
            "action_type": action_type,
            "payload": payload,
            "requested_by": str(requested_by),
            "reason": reason,
        }
        response = self._socket_request(endpoint=endpoint, payload=req)
        if not response:
            return None

        decision = self._normalize_decision(str(response.get("decision", "")).strip())
        if not decision and "status" in response:
            decision = self._normalize_decision(str(response.get("status", "")).strip())
        if not decision and isinstance(response.get("approved"), bool):
            decision = "approved" if bool(response.get("approved")) else "denied"
        if not decision:
            return None

        response_id = str(response.get("id", "")).strip() or request_id
        message = str(response.get("message", "")).strip()
        return ExternalApprovalDecision(decision=decision, request_id=response_id, message=message)

    def socket_reachable(self) -> tuple[bool, str]:
        endpoint = self._load_endpoint()
        if not endpoint:
            return False, "External approvals config not available."
        if endpoint.transport == "tcp":
            try:
                with socket.create_connection((endpoint.host, int(endpoint.port)), timeout=self.timeout) as client:
                    client.settimeout(self.timeout)
                    ok, reason = self._perform_handshake(client, endpoint.token)
                    if ok:
                        return True, f"Connected and authenticated to tcp://{endpoint.host}:{endpoint.port}"
                    return False, f"Connected but auth failed: {reason}"
            except Exception as exc:
                return False, f"TCP endpoint not reachable: {exc}"
        if os.name == "nt" and not hasattr(socket, "AF_UNIX"):
            return False, "AF_UNIX is not available on this platform/runtime. Configure TCP endpoint in approvals config."
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout)
                client.connect(endpoint.socket_path)
                ok, reason = self._perform_handshake(client, endpoint.token)
                if ok:
                    return True, f"Connected and authenticated to {endpoint.socket_path}"
                return False, f"Connected but auth failed: {reason}"
        except Exception as exc:
            return False, f"Socket not reachable: {exc}"
