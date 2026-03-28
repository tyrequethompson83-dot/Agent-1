from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.dashboard_state import DashboardSession, DashboardSessionStore
from agent1.dashboard_ui import dashboard_html
from agent1.diagnostics import Doctor
from agent1.service_manager import ServiceManager


class ApprovalActionRequest(BaseModel):
    actor: str = "dashboard-ui"
    reason: str = ""


class CreateSessionRequest(BaseModel):
    title: str = ""


class ChatMessageRequest(BaseModel):
    text: str = ""


class ProviderUpdateRequest(BaseModel):
    provider: str = ""


class ModelUpdateRequest(BaseModel):
    model: str = ""
    clear: bool = False


def _load_json(path: Path, fallback: dict | list) -> dict | list:
    if not path.exists():
        return fallback
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return fallback
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _known_dashboard_user_ids(settings: Settings) -> list[str]:
    payload = _load_json(settings.session_jobs_path, {"jobs": {}})
    rows = payload.get("jobs", {}) if isinstance(payload, dict) else {}
    out: set[str] = set()
    if isinstance(rows, dict):
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            user_id = str(row.get("user_id", "")).strip()
            if user_id.startswith("dashboard:"):
                out.add(user_id)
    return sorted(out)


def _doctor_snapshot(settings: Settings) -> dict[str, object]:
    rows = Doctor(settings).run()
    failed = len([row for row in rows if not row.ok])
    return {
        "ok": failed == 0,
        "passed": len(rows) - failed,
        "total": len(rows),
        "rows": [asdict(row) for row in rows],
        "report": Doctor(settings).report_text(),
    }


def _serialize_session(session: DashboardSession) -> dict[str, object]:
    return asdict(session)


def _session_runtime(orchestrator: AgentOrchestrator, session: DashboardSession) -> dict[str, object]:
    provider_status = orchestrator.get_provider_status(session.user_id)
    policy_status = orchestrator.get_tool_policy_status(session.user_id)
    return {
        "user_id": session.user_id,
        "provider_status": provider_status,
        "available_providers": orchestrator.list_available_providers(),
        "policy_status": policy_status,
        "available_tool_profiles": orchestrator.list_tool_profiles(),
        "usage_report": orchestrator.usage_report(session.user_id),
    }


def _config_summary(settings: Settings, orchestrator: AgentOrchestrator) -> dict[str, object]:
    return {
        "app_name": settings.app_name,
        "chat_adapter": settings.chat_adapter,
        "llm": {
            "default_provider": settings.llm_default_provider,
            "default_model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "available_providers": orchestrator.list_available_providers(),
        },
        "paths": {
            "data_dir": str(settings.data_dir),
            "workspace_dir": str(settings.workspace_profile_path),
            "logs_dir": str(settings.app_log_path.parent),
            "approval_store": str(settings.approval_store_path),
            "session_jobs": str(settings.session_jobs_path),
            "session_history": str(settings.session_history_path),
            "plugins_registry": str(settings.plugins_registry_path),
        },
        "integrations": {
            "telegram": bool(settings.telegram_bot_token.strip()),
            "discord": bool(settings.discord_bot_token.strip()),
            "slack": bool(settings.slack_bot_token.strip()),
            "whatsapp": bool(settings.whatsapp_access_token.strip()),
            "bridge": bool(settings.bridge_auth_token.strip()),
            "email": bool(settings.email_enabled),
            "calendar": bool(settings.calendar_enabled),
        },
        "session_engine": {
            "max_concurrency": settings.session_max_concurrency,
        },
    }


def create_dashboard_app(
    settings: Settings,
    *,
    orchestrator: AgentOrchestrator | None = None,
    service_manager: ServiceManager | None = None,
    session_store: DashboardSessionStore | None = None,
) -> FastAPI:
    settings.ensure_paths()
    orchestrator = orchestrator or AgentOrchestrator(settings)
    approvals = orchestrator.approvals
    session_store = session_store or DashboardSessionStore(settings)
    service_manager = service_manager or ServiceManager()
    session_store.ensure_default_session(_known_dashboard_user_ids(settings))

    app = FastAPI(title="Agent 1 Dashboard", version="0.2.0")

    def require_session(session_id: str) -> DashboardSession:
        session = session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Unknown dashboard session `{session_id}`.")
        return session

    def session_payload(session: DashboardSession, *, msg_limit: int = 200, job_limit: int = 25) -> dict[str, object]:
        fresh = session_store.get_session(session.id) or session
        return {
            "session": _serialize_session(fresh),
            "messages": [asdict(row) for row in session_store.list_messages(fresh.id, limit=msg_limit)],
            "jobs": orchestrator.list_session_jobs(fresh.user_id, limit=job_limit),
            "runtime": _session_runtime(orchestrator, fresh),
        }

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/api/health")
    def health() -> dict[str, object]:
        snapshot = _doctor_snapshot(settings)
        default_session = session_store.ensure_default_session(_known_dashboard_user_ids(settings))
        runtime = _session_runtime(orchestrator, default_session)
        return {
            "ok": bool(snapshot["ok"]),
            "app": settings.app_name,
            "chat_adapter": settings.chat_adapter,
            "default_session_id": default_session.id,
            "provider": runtime["provider_status"]["provider"],
            "model": runtime["provider_status"]["model"],
        }

    @app.get("/api/doctor")
    def doctor_report() -> dict[str, object]:
        return _doctor_snapshot(settings)

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        snapshot = _doctor_snapshot(settings)
        sessions = session_store.list_sessions(limit=12)
        active = sessions[0] if sessions else session_store.ensure_default_session(_known_dashboard_user_ids(settings))
        return {
            "health": {"ok": bool(snapshot["ok"]), "passed": snapshot["passed"], "total": snapshot["total"]},
            "active_session_id": active.id,
            "pending_approvals_count": len(approvals.list_pending(limit=200)),
            "session_count": len(session_store.list_sessions(limit=500)),
            "workspace_dir": str(settings.workspace_profile_path),
            "data_dir": str(settings.data_dir),
            "provider_status": orchestrator.get_provider_status(active.user_id),
            "usage_report": orchestrator.usage_report(active.user_id),
            "recent_sessions": [_serialize_session(row) for row in sessions],
            "recent_jobs": orchestrator.list_session_jobs(active.user_id, limit=8),
            "doctor_report": snapshot["report"],
        }

    @app.get("/api/service")
    def service_status() -> dict[str, object]:
        ok, output = service_manager.status()
        return {"ok": ok, "output": output}

    @app.get("/api/chat/sessions")
    def list_sessions(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, object]:
        default_session = session_store.ensure_default_session(_known_dashboard_user_ids(settings))
        sessions = session_store.list_sessions(limit=limit)
        return {
            "items": [_serialize_session(row) for row in sessions],
            "default_session_id": default_session.id,
        }

    @app.post("/api/chat/sessions")
    def create_session(
        payload: CreateSessionRequest = Body(default_factory=CreateSessionRequest),
    ) -> dict[str, object]:
        session = session_store.create_session(title=payload.title)
        return {
            "session": _serialize_session(session),
            "items": [_serialize_session(row) for row in session_store.list_sessions(limit=100)],
        }

    @app.get("/api/chat/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, object]:
        return session_payload(require_session(session_id))

    @app.get("/api/chat/sessions/{session_id}/messages")
    def get_session_messages(
        session_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        session = require_session(session_id)
        return [asdict(row) for row in session_store.list_messages(session.id, limit=limit)]

    @app.get("/api/chat/sessions/{session_id}/runtime")
    def get_session_runtime(session_id: str) -> dict[str, object]:
        return _session_runtime(orchestrator, require_session(session_id))

    @app.get("/api/chat/sessions/{session_id}/jobs")
    def get_session_jobs(
        session_id: str,
        limit: int = Query(default=25, ge=1, le=200),
    ) -> list[dict[str, str]]:
        session = require_session(session_id)
        return orchestrator.list_session_jobs(session.user_id, limit=limit)

    @app.post("/api/chat/sessions/{session_id}/messages")
    def post_session_message(
        session_id: str,
        payload: ChatMessageRequest = Body(default_factory=ChatMessageRequest),
    ) -> dict[str, object]:
        session = require_session(session_id)
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Message text cannot be empty.")

        session_store.append_message(session.id, "user", text)
        try:
            reply = orchestrator.process_message(session.user_id, text)
            kind = "message"
        except Exception as exc:
            reply = f"Specialist error: {exc}"
            kind = "error"
        session_store.append_message(session.id, "assistant", reply, kind=kind)
        return session_payload(session)

    @app.post("/api/chat/sessions/{session_id}/provider")
    def update_session_provider(
        session_id: str,
        payload: ProviderUpdateRequest = Body(default_factory=ProviderUpdateRequest),
    ) -> dict[str, object]:
        session = require_session(session_id)
        ok, message = orchestrator.set_provider_for_user(session.user_id, payload.provider)
        return {"ok": ok, "message": message, "runtime": _session_runtime(orchestrator, session)}

    @app.post("/api/chat/sessions/{session_id}/model")
    def update_session_model(
        session_id: str,
        payload: ModelUpdateRequest = Body(default_factory=ModelUpdateRequest),
    ) -> dict[str, object]:
        session = require_session(session_id)
        if payload.clear or not payload.model.strip():
            ok, message = orchestrator.clear_model_override_for_user(session.user_id)
        else:
            ok, message = orchestrator.set_model_for_user(session.user_id, payload.model)
        return {"ok": ok, "message": message, "runtime": _session_runtime(orchestrator, session)}

    @app.get("/api/approvals/pending")
    def pending_approvals(limit: int = Query(default=30, ge=1, le=200)) -> list[dict[str, object]]:
        rows = approvals.list_pending(limit=limit)
        return [asdict(row) for row in rows]

    @app.post("/api/approvals/{approval_id}/approve")
    def approve_approval(
        approval_id: str,
        payload: ApprovalActionRequest = Body(default_factory=ApprovalActionRequest),
    ) -> dict[str, object]:
        ok, message = approvals.approve(approval_id=approval_id, approved_by=payload.actor.strip() or "dashboard-ui")
        return {"ok": ok, "message": message, "approval_id": approval_id}

    @app.post("/api/approvals/{approval_id}/deny")
    def deny_approval(
        approval_id: str,
        payload: ApprovalActionRequest = Body(default_factory=ApprovalActionRequest),
    ) -> dict[str, object]:
        ok, message = approvals.deny(
            approval_id=approval_id,
            denied_by=payload.actor.strip() or "dashboard-ui",
            reason=payload.reason,
        )
        return {"ok": ok, "message": message, "approval_id": approval_id}

    @app.post("/api/jobs/{job_id}/resume")
    def resume_job(job_id: str) -> dict[str, object]:
        ok, message = orchestrator.resume_session_job(job_id)
        return {"ok": ok, "message": message, "job_id": job_id}

    @app.get("/api/skills")
    def skills() -> list[dict[str, str]]:
        return orchestrator.list_dynamic_skill_states()

    @app.get("/api/plugins")
    def plugins() -> list[dict[str, str]]:
        return orchestrator.list_plugins()

    @app.get("/api/config")
    def config_summary() -> dict[str, object]:
        return _config_summary(settings, orchestrator)

    return app


def run_dashboard(settings: Settings, host: str = "127.0.0.1", port: int = 8765) -> None:
    app = create_dashboard_app(settings)
    uvicorn.run(app, host=host, port=int(port), log_level="info")
