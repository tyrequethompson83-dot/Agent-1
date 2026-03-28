from __future__ import annotations

from dataclasses import asdict

import uvicorn
from fastapi import Body, FastAPI, Query
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

from agent1.approvals_bridge import ExternalApprovalsBridge
from agent1.config import Settings
from agent1.diagnostics import Doctor
from agent1.tools.approval import ApprovalManager


class ApprovalActionRequest(BaseModel):
    actor: str = "dashboard-ui"
    reason: str = ""


def _dashboard_html() -> str:
    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Agent 1 Dashboard</title>
    <style>
      :root { --bg:#0b1220; --card:#121a2b; --ink:#e6edf7; --muted:#9fb0cc; --accent:#39a0ff; --ok:#19c37d; --fail:#ff5d5d; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; background:linear-gradient(180deg,#0b1220,#0f1728); color:var(--ink); }
      .wrap { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
      .row { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }
      .card { background: var(--card); border:1px solid #223252; border-radius: 12px; padding: 14px; }
      h1 { margin: 0 0 16px; font-size: 24px; }
      h2 { margin: 0 0 8px; font-size: 16px; color: var(--muted); }
      pre { white-space: pre-wrap; font-size: 12px; line-height: 1.5; color: #d7e3f7; background:#0d1526; border-radius:8px; padding:10px; border:1px solid #223252; }
      button { border:0; background:var(--accent); color:white; padding:8px 12px; border-radius:8px; cursor:pointer; font-weight:600; }
      button.deny { background:#a32121; }
      .pill { display:inline-block; font-size:12px; border-radius:999px; padding:2px 8px; margin-left:6px; }
      .ok { background: #103924; color: #8df0bf; border:1px solid #1f7348; }
      .fail { background:#3c1212; color:#ff9b9b; border:1px solid #8a2323; }
      .approval { border:1px solid #243557; border-radius:10px; padding:10px; margin-bottom:10px; background:#0d1526; }
      .meta { color: var(--muted); font-size:12px; margin-bottom:8px; }
      .actions { display:flex; gap:8px; margin-top:8px; }
      @media (max-width: 860px) { .row { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Agent 1 Dashboard <span id="health" class="pill">checking</span></h1>
      <div class="row">
        <div class="card">
          <h2>Doctor</h2>
          <p><button onclick="refreshDoctor()">Refresh Doctor</button></p>
          <pre id="doctor">Loading...</pre>
        </div>
        <div class="card">
          <h2>Pending Approvals</h2>
          <p><button onclick="refreshApprovals()">Refresh Approvals</button></p>
          <div id="approvals">Loading...</div>
        </div>
      </div>
    </div>
    <script>
      async function loadHealth() {
        const res = await fetch('/api/health');
        const data = await res.json();
        const el = document.getElementById('health');
        if (data.ok) { el.className = 'pill ok'; el.textContent = 'healthy'; }
        else { el.className = 'pill fail'; el.textContent = 'degraded'; }
      }
      async function refreshDoctor() {
        const res = await fetch('/api/doctor');
        const data = await res.json();
        document.getElementById('doctor').textContent = data.report || '';
      }
      async function refreshApprovals() {
        const res = await fetch('/api/approvals/pending?limit=30');
        const rows = await res.json();
        const root = document.getElementById('approvals');
        if (!rows.length) { root.innerHTML = '<pre>No pending approvals.</pre>'; return; }
        root.innerHTML = rows.map(r => `
          <div class="approval">
            <div class="meta">${r.id} | ${r.action_type} | ${r.requested_by}</div>
            <pre>${r.reason || ''}</pre>
            <div class="actions">
              <button onclick="approve('${r.id}')">Approve</button>
              <button class="deny" onclick="denyApproval('${r.id}')">Deny</button>
            </div>
          </div>
        `).join('');
      }
      async function approve(id) {
        const res = await fetch(`/api/approvals/${id}/approve`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ actor: 'dashboard-ui' }) });
        const data = await res.json();
        alert(data.message || (data.ok ? 'Approved' : 'Failed'));
        refreshApprovals();
      }
      async function denyApproval(id) {
        const reason = prompt('Optional deny reason:', '') || '';
        const res = await fetch(`/api/approvals/${id}/deny`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ actor: 'dashboard-ui', reason }) });
        const data = await res.json();
        alert(data.message || (data.ok ? 'Denied' : 'Failed'));
        refreshApprovals();
      }
      loadHealth(); refreshDoctor(); refreshApprovals();
    </script>
  </body>
</html>"""


def create_dashboard_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent 1 Dashboard", version="0.1.0")
    approvals = ApprovalManager(
        store_path=settings.approval_store_path,
        external_bridge=ExternalApprovalsBridge(settings),
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _dashboard_html()

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {"ok": True, "app": settings.app_name}

    @app.get("/api/doctor")
    def doctor_report() -> dict[str, str]:
        report = Doctor(settings).report_text()
        return {"report": report}

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

    return app


def run_dashboard(settings: Settings, host: str = "127.0.0.1", port: int = 8765) -> None:
    app = create_dashboard_app(settings)
    uvicorn.run(app, host=host, port=int(port), log_level="info")
