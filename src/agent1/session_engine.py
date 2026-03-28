from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from agent1.config import Settings


def _utc_ts() -> int:
    return int(time.time())


@dataclass
class SessionJob:
    id: str
    user_id: str
    user_input: str
    status: str
    created_ts: int
    started_ts: int
    completed_ts: int
    error: str
    output_preview: str


class SessionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs_path: Path = settings.session_jobs_path
        self.history_path: Path = settings.session_history_path
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._user_locks: dict[str, threading.Lock] = {}
        self._global_slots = threading.Semaphore(max(1, int(settings.session_max_concurrency)))
        if not self.jobs_path.exists():
            self._save({"jobs": {}})

    @staticmethod
    def _empty_jobs_payload() -> dict:
        return {"jobs": {}}

    def _load(self) -> dict:
        if not self.jobs_path.exists():
            return self._empty_jobs_payload()

        try:
            raw = self.jobs_path.read_text(encoding="utf-8-sig").strip()
        except UnicodeDecodeError:
            raw = self.jobs_path.read_text(encoding="utf-8", errors="ignore").strip()

        if not raw:
            return self._empty_jobs_payload()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._empty_jobs_payload()

        if not isinstance(payload, dict):
            return self._empty_jobs_payload()

        jobs = payload.get("jobs")
        if isinstance(jobs, dict):
            return payload

        # Accept legacy/list-shaped payloads and normalize to keyed dict.
        normalized: dict[str, dict] = {}
        if isinstance(jobs, list):
            for row in jobs:
                if isinstance(row, dict):
                    job_id = str(row.get("id", "")).strip()
                    if job_id:
                        normalized[job_id] = row
        payload["jobs"] = normalized
        return payload

    def _save(self, data: dict) -> None:
        self.jobs_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _user_lock(self, user_id: str) -> threading.Lock:
        with self._lock:
            lock = self._user_locks.get(user_id)
            if lock is None:
                lock = threading.Lock()
                self._user_locks[user_id] = lock
            return lock

    @staticmethod
    def _clip(value: str, limit: int = 280) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "... [truncated]"

    def _write_history_event(self, payload: dict) -> None:
        payload = dict(payload)
        payload["ts"] = _utc_ts()
        with self._lock:
            with self.history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def _create_job(self, user_id: str, user_input: str) -> SessionJob:
        job = SessionJob(
            id=f"J-{uuid4().hex[:10]}",
            user_id=str(user_id),
            user_input=user_input,
            status="queued",
            created_ts=_utc_ts(),
            started_ts=0,
            completed_ts=0,
            error="",
            output_preview="",
        )
        with self._lock:
            data = self._load()
            data.setdefault("jobs", {})[job.id] = job.__dict__
            self._save(data)
        self._write_history_event(
            {
                "event": "session_job_created",
                "job_id": job.id,
                "user_id": job.user_id,
                "status": job.status,
            }
        )
        return job

    def _update_job(self, job_id: str, **changes) -> SessionJob | None:
        with self._lock:
            data = self._load()
            row = data.get("jobs", {}).get(job_id)
            if not isinstance(row, dict):
                return None
            row.update(changes)
            data["jobs"][job_id] = row
            self._save(data)
            return SessionJob(**row)

    def list_jobs(self, user_id: str, limit: int = 20) -> list[SessionJob]:
        with self._lock:
            data = self._load()
            rows = [
                SessionJob(**row)
                for row in data.get("jobs", {}).values()
                if isinstance(row, dict) and str(row.get("user_id", "")) == str(user_id)
            ]
        rows.sort(key=lambda item: item.created_ts, reverse=True)
        return rows[:limit]

    def run_sync(self, user_id: str, user_input: str, handler: Callable[[str, str], str]) -> str:
        job = self._create_job(user_id=str(user_id), user_input=user_input)
        user_lock = self._user_lock(str(user_id))

        with self._global_slots:
            with user_lock:
                self._update_job(job.id, status="running", started_ts=_utc_ts())
                self._write_history_event(
                    {
                        "event": "session_job_started",
                        "job_id": job.id,
                        "user_id": str(user_id),
                    }
                )
                try:
                    output = handler(str(user_id), user_input)
                    self._update_job(
                        job.id,
                        status="completed",
                        completed_ts=_utc_ts(),
                        output_preview=self._clip(output or ""),
                    )
                    self._write_history_event(
                        {
                            "event": "session_job_completed",
                            "job_id": job.id,
                            "user_id": str(user_id),
                        }
                    )
                    return output
                except Exception as exc:
                    self._update_job(
                        job.id,
                        status="failed",
                        completed_ts=_utc_ts(),
                        error=str(exc),
                    )
                    self._write_history_event(
                        {
                            "event": "session_job_failed",
                            "job_id": job.id,
                            "user_id": str(user_id),
                            "error": str(exc),
                        }
                    )
                    raise

    def resume_job(self, job_id: str, handler: Callable[[str, str], str]) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            row = data.get("jobs", {}).get(job_id)
            if not isinstance(row, dict):
                return False, f"Unknown job `{job_id}`."
            status = str(row.get("status", ""))
            if status not in {"failed", "completed"}:
                return False, f"Job `{job_id}` is `{status}` and cannot be resumed."
            user_id = str(row.get("user_id", ""))
            user_input = str(row.get("user_input", ""))

        try:
            self.run_sync(user_id=user_id, user_input=user_input, handler=handler)
            return True, f"Resumed job `{job_id}` by creating a new execution run."
        except Exception as exc:
            return False, f"Resume failed: {exc}"
