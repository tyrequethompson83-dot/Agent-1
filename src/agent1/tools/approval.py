from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent1.approvals_bridge import ExternalApprovalsBridge


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ApprovalRecord:
    id: str
    action_type: str
    payload: dict[str, Any]
    fingerprint: str
    reason: str
    requested_by: str
    status: str = "pending"
    approved_by: str | None = None
    denied_by: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    approved_at: str | None = None
    denied_at: str | None = None
    consumed_at: str | None = None


class ApprovalManager:
    def __init__(self, store_path: Path, external_bridge: ExternalApprovalsBridge | None = None):
        self.store_path = store_path
        self.external_bridge = external_bridge
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.store_path.exists():
            self._save({"records": {}})

    def _load(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"records": {}}
        raw = self.store_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {"records": {}}
        return json.loads(raw)

    def _save(self, data: dict[str, Any]) -> None:
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _fingerprint(action_type: str, payload: dict[str, Any]) -> str:
        digest_input = json.dumps({"action_type": action_type, "payload": payload}, sort_keys=True, default=str)
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def request_approval(
        self,
        action_type: str,
        payload: dict[str, Any],
        requested_by: str,
        reason: str,
    ) -> ApprovalRecord:
        fingerprint = self._fingerprint(action_type, payload)
        with self._lock:
            data = self._load()
            records = data["records"]

            for item in records.values():
                if item["fingerprint"] == fingerprint and item["status"] in {"pending", "denied"}:
                    return ApprovalRecord(**item)

            if self.external_bridge:
                decision = self.external_bridge.request_decision(
                    action_type=action_type,
                    payload=payload,
                    requested_by=requested_by,
                    reason=reason,
                )
                if decision:
                    approval = ApprovalRecord(
                        id=f"A-{uuid4().hex[:10]}",
                        action_type=action_type,
                        payload=payload,
                        fingerprint=fingerprint,
                        reason=reason,
                        requested_by=requested_by,
                        status=decision.decision,
                    )
                    if decision.decision == "approved":
                        approval.approved_by = f"external:{decision.request_id}"
                        approval.approved_at = _utc_now_iso()
                    if decision.decision == "denied":
                        approval.reason = f"{reason} | external: {decision.message or decision.request_id}"
                    records[approval.id] = asdict(approval)
                    self._save(data)
                    return approval

            approval = ApprovalRecord(
                id=f"A-{uuid4().hex[:10]}",
                action_type=action_type,
                payload=payload,
                fingerprint=fingerprint,
                reason=reason,
                requested_by=requested_by,
            )
            records[approval.id] = asdict(approval)
            self._save(data)
            return approval

    def approve(self, approval_id: str, approved_by: str) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            records = data["records"]
            row = records.get(approval_id)
            if not row:
                return False, f"Approval id `{approval_id}` was not found."
            if row["status"] == "approved":
                return True, f"Approval `{approval_id}` was already approved."
            row["status"] = "approved"
            row["approved_by"] = approved_by
            row["approved_at"] = _utc_now_iso()
            row["denied_by"] = None
            row["denied_at"] = None
            self._save(data)
            return True, f"Approved `{approval_id}`. Re-send the original request."

    def deny(self, approval_id: str, denied_by: str, reason: str = "") -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            records = data["records"]
            row = records.get(approval_id)
            if not row:
                return False, f"Approval id `{approval_id}` was not found."
            if row["status"] == "denied":
                return True, f"Approval `{approval_id}` was already denied."

            row["status"] = "denied"
            row["denied_by"] = denied_by
            row["denied_at"] = _utc_now_iso()
            if reason.strip():
                row["reason"] = f"{row.get('reason', '').strip()} | denied: {reason.strip()}".strip(" |")
            self._save(data)
            return True, f"Denied `{approval_id}`."

    def list_pending(self, limit: int = 20) -> list[ApprovalRecord]:
        with self._lock:
            data = self._load()
            rows = [ApprovalRecord(**item) for item in data["records"].values() if item.get("status") == "pending"]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[:limit]

    def consume_if_approved(self, action_type: str, payload: dict[str, Any]) -> bool:
        fingerprint = self._fingerprint(action_type, payload)
        with self._lock:
            data = self._load()
            records = data["records"]

            candidates: list[dict[str, Any]] = [
                item
                for item in records.values()
                if item.get("fingerprint") == fingerprint
                and item.get("status") == "approved"
                and item.get("consumed_at") is None
            ]
            if not candidates:
                return False

            candidates.sort(key=lambda item: item.get("approved_at") or "")
            target = candidates[-1]
            target["consumed_at"] = _utc_now_iso()
            self._save(data)
            return True
