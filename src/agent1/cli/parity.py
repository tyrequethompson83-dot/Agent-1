from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from agent1.approvals_bridge import ExternalApprovalsBridge
from agent1.config import PROJECT_ROOT, Settings
from agent1.dashboard import create_dashboard_app
from agent1.diagnostics import Doctor
from agent1.plugins.manager import PluginManager
from agent1.session_engine import SessionEngine
from agent1.tools.approval import ApprovalManager
from agent1.tools.loader import UniversalSkillLoader
from agent1.tools.safe_shell import SafeShellTool
from agent1.workspace_profile import WorkspaceProfile


@dataclass
class ParityCheckResult:
    name: str
    ok: bool
    required: bool
    details: str
    duration_ms: int


def _parse_approval_id(text: str) -> str:
    match = re.search(r"/approve\s+([A-Za-z0-9\-]+)", text or "")
    if not match:
        return ""
    return match.group(1).strip()


def _line(text: str) -> str:
    return str(text).replace("\n", " ").strip()


def _project_file(relative_path: str) -> Path:
    return (PROJECT_ROOT / relative_path).resolve()


def _parity_root(settings: Settings) -> Path:
    path = (settings.data_dir / "parity").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mock_external_approvals_server(token: str) -> tuple[int, threading.Thread]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    port = int(server.getsockname()[1])
    server.listen(1)

    def recv_json_line(conn: socket.socket) -> dict:
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 131072:
                break
        if not buf:
            return {}
        try:
            data = json.loads(buf.decode("utf-8", errors="ignore").strip())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def send_json_line(conn: socket.socket, payload: dict) -> None:
        conn.sendall((json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8"))

    def worker() -> None:
        try:
            conn, _addr = server.accept()
            with conn:
                conn.settimeout(2)
                _hello = recv_json_line(conn)
                send_json_line(conn, {"type": "hello", "protocol": "exec-approvals.v1"})
                auth = recv_json_line(conn)
                if str(auth.get("token", "")).strip() != token:
                    send_json_line(conn, {"ok": False, "message": "bad_token"})
                    return
                send_json_line(conn, {"ok": True})
                req = recv_json_line(conn)
                req_id = str(req.get("id", "")).strip() or "mock-req"
                send_json_line(conn, {"decision": "approved", "id": req_id, "message": "approved_by_mock"})
        except Exception:
            return
        finally:
            try:
                server.close()
            except Exception:
                pass

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return port, thread


def run_parity_check(settings: Settings, strict: bool = False) -> tuple[int, list[ParityCheckResult], dict]:
    results: list[ParityCheckResult] = []
    parity_root = _parity_root(settings)

    def run_check(name: str, required: bool, fn: Callable[[], tuple[bool, str]]) -> None:
        started = time.perf_counter()
        try:
            ok, details = fn()
        except Exception as exc:
            ok = False
            details = f"Exception: {exc}"
        duration_ms = int((time.perf_counter() - started) * 1000)
        results.append(
            ParityCheckResult(
                name=name,
                ok=bool(ok),
                required=bool(required),
                details=_line(details),
                duration_ms=duration_ms,
            )
        )

    def check_install_scripts() -> tuple[bool, str]:
        required_files = [
            "scripts/install.ps1",
            "scripts/install.sh",
            "scripts/bootstrap.ps1",
            "scripts/bootstrap.sh",
        ]
        missing = [path for path in required_files if not _project_file(path).exists()]
        if missing:
            return False, "Missing scripts: " + ", ".join(missing)
        return True, "Installer and bootstrap scripts present."

    def check_workspace_scaffold() -> tuple[bool, str]:
        profile = WorkspaceProfile(settings.workspace_profile_path)
        profile.ensure_scaffold()
        missing = [name for name in profile.CORE_FILES if not (settings.workspace_profile_path / name).exists()]
        if missing:
            return False, "Missing core workspace files: " + ", ".join(missing)
        return True, f"Workspace scaffold verified at {settings.workspace_profile_path}"

    def check_doctor_runtime() -> tuple[bool, str]:
        doctor = Doctor(settings)
        rows = doctor.run()
        required_names = {"python_version", "paths", "skills_dir", "plugins_registry"}
        failed = [row.name for row in rows if row.name in required_names and not row.ok]
        if failed:
            return False, "Doctor failed critical checks: " + ", ".join(failed)
        return True, "Doctor critical checks passed."

    def check_adapter_modules() -> tuple[bool, str]:
        modules = [
            "agent1.integrations.telegram_bot",
            "agent1.integrations.discord_bot",
            "agent1.integrations.slack_bot",
            "agent1.integrations.whatsapp_bot",
            "agent1.integrations.bridge_webhook",
        ]
        missing = [name for name in modules if importlib.util.find_spec(name) is None]
        if missing:
            return False, "Missing adapter modules: " + ", ".join(missing)
        return True, "All first-class adapter modules importable."

    def check_skill_loader() -> tuple[bool, str]:
        loader = UniversalSkillLoader(settings=settings, policy_manager=None, usage_meter=None)
        enabled = loader.reindex(force=True)
        discovered = len(loader.list_skill_states(refresh=False))
        if discovered <= 0:
            return False, "No skills discovered under skills root."
        if enabled <= 0:
            return False, f"{discovered} skills discovered but none enabled."
        return True, f"Skills discovered={discovered} enabled={enabled}."

    def check_plugin_registry() -> tuple[bool, str]:
        manager = PluginManager(settings)
        _plugins = manager.list_plugins()
        return True, f"Plugin registry reachable at {settings.plugins_registry_path}"

    def check_approval_lifecycle() -> tuple[bool, str]:
        store_path = parity_root / "approvals_lifecycle.json"
        if store_path.exists():
            store_path.write_text("", encoding="utf-8")
        manager = ApprovalManager(store_path=store_path, external_bridge=None)
        record = manager.request_approval(
            action_type="file_write",
            payload={"path": "demo.txt", "content": "hello"},
            requested_by="parity-user",
            reason="parity test",
        )
        ok_approve, _msg_approve = manager.approve(record.id, approved_by="parity")
        consumed = manager.consume_if_approved("file_write", {"path": "demo.txt", "content": "hello"})
        record2 = manager.request_approval(
            action_type="shell",
            payload={"command": "echo hi"},
            requested_by="parity-user",
            reason="parity test 2",
        )
        ok_deny, _msg_deny = manager.deny(record2.id, denied_by="parity", reason="blocked in parity")
        if not (ok_approve and consumed and ok_deny):
            return False, "Approval lifecycle failed (approve/consume/deny)."
        return True, "Approval lifecycle (approve, consume, deny) passed."

    def check_safe_shell_gate() -> tuple[bool, str]:
        store_path = parity_root / "approvals_shell.json"
        if store_path.exists():
            store_path.write_text("", encoding="utf-8")
        manager = ApprovalManager(store_path=store_path, external_bridge=None)
        local_settings = settings.model_copy(deep=True)
        local_settings.auto_approve_risky_actions = False
        python_bin = Path(sys.executable).resolve()
        local_settings.safe_shell_allowed_commands = str(python_bin)
        local_settings.safe_shell_workdir = parity_root
        tool = SafeShellTool(settings=local_settings, approvals=manager)
        first = tool.run(user_id="parity-user", command=f'"{python_bin}" --version')
        approval_id = _parse_approval_id(first)
        if not approval_id:
            return False, "Expected approval request for safe_shell."
        ok, _msg = manager.approve(approval_id=approval_id, approved_by="parity")
        second = tool.run(user_id="parity-user", command=f'"{python_bin}" --version')
        if not ok or "Command succeeded" not in second:
            return False, "Approved safe_shell execution did not succeed."
        return True, "safe_shell approval gate behavior passed."

    def check_session_engine() -> tuple[bool, str]:
        local_settings = settings.model_copy(deep=True)
        local_settings.session_jobs_path = parity_root / "jobs.json"
        local_settings.session_history_path = parity_root / "history.jsonl"
        local_settings.session_max_concurrency = 2
        engine = SessionEngine(local_settings)
        output = engine.run_sync("parity-user", "hello", lambda user, text: f"{user}:{text.upper()}")
        if "HELLO" not in output:
            return False, "Session run_sync output mismatch."
        jobs = engine.list_jobs("parity-user", limit=5)
        if not jobs:
            return False, "No session jobs recorded."
        ok_resume, msg = engine.resume_job(jobs[0].id, handler=lambda user, text: f"{user}:{text}")
        if not ok_resume:
            return False, f"Resume job failed: {msg}"
        return True, "Session engine queue/history/resume checks passed."

    def check_external_approvals_tcp() -> tuple[bool, str]:
        token = "parity-token"
        port, thread = _mock_external_approvals_server(token=token)
        time.sleep(0.05)

        config_path = parity_root / f"exec-approvals-{uuid4().hex[:8]}.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "protocol": "exec-approvals.v1",
                    "tcp": {"host": "127.0.0.1", "port": port},
                    "socket": {"path": "", "token": token},
                    "permissions": {"default": "ask", "allow": [], "deny": []},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        bridge_settings = settings.model_copy(deep=True)
        bridge_settings.external_approvals_enabled = True
        bridge_settings.external_approvals_config_path = config_path
        bridge_settings.external_approvals_timeout_seconds = 2
        bridge = ExternalApprovalsBridge(bridge_settings)
        decision = bridge.request_decision(
            action_type="shell",
            payload={"command": "echo parity"},
            requested_by="parity-user",
            reason="parity transport check",
        )
        thread.join(timeout=1.5)
        if not decision or decision.decision != "approved":
            return False, "TCP external approvals handshake/authorize failed."
        return True, f"TCP external approvals path verified on localhost:{port}"

    def check_dashboard_api() -> tuple[bool, str]:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            return False, f"fastapi test client unavailable: {exc}"

        local_settings = settings.model_copy(deep=True)
        local_settings.external_approvals_enabled = False
        local_settings.data_dir = parity_root / "dashboard_data"
        local_settings.safe_files_root = local_settings.data_dir / "safe_workspace"
        local_settings.safe_shell_workdir = local_settings.data_dir / "safe_workspace"
        local_settings.markdown_memory_path = local_settings.data_dir / "memory"
        local_settings.vector_memory_path = local_settings.data_dir / "chroma"
        local_settings.approval_store_path = local_settings.data_dir / "approvals" / "pending.json"
        local_settings.provider_preferences_path = local_settings.data_dir / "approvals" / "provider_preferences.json"
        local_settings.tool_policy_store_path = local_settings.data_dir / "approvals" / "tool_policy.json"
        local_settings.app_log_path = local_settings.data_dir / "logs" / "app.log"
        local_settings.tool_log_path = local_settings.data_dir / "logs" / "tool_calls.log"
        local_settings.agentguard_audit_log_path = local_settings.data_dir / "logs" / "agentguard_audit.log"
        local_settings.usage_meter_path = local_settings.data_dir / "logs" / "usage_meter.jsonl"
        local_settings.workspace_profile_path = parity_root / "dashboard_workspace"
        local_settings.skills_root_path = local_settings.workspace_profile_path / "skills"
        local_settings.skills_registry_path = local_settings.skills_root_path / "registry.json"
        local_settings.plugins_root_path = local_settings.workspace_profile_path / "plugins"
        local_settings.plugins_registry_path = local_settings.plugins_root_path / "registry.json"
        local_settings.session_jobs_path = local_settings.data_dir / "sessions" / "jobs.json"
        local_settings.session_history_path = local_settings.data_dir / "sessions" / "history.jsonl"
        if local_settings.approval_store_path.exists():
            local_settings.approval_store_path.write_text("", encoding="utf-8")

        manager = ApprovalManager(store_path=local_settings.approval_store_path, external_bridge=None)
        record = manager.request_approval(
            action_type="send_email",
            payload={"to": "demo@example.com"},
            requested_by="parity-user",
            reason="dashboard parity",
        )

        class FakeOrchestrator:
            def __init__(self, approval_manager: ApprovalManager):
                self.approvals = approval_manager
                self._prefs: dict[str, dict[str, str]] = {}
                self._jobs: dict[str, list[dict[str, str]]] = {}

            def _status(self, user_id: str) -> dict[str, str]:
                pref = self._prefs.setdefault(str(user_id), {"provider": "custom", "model": "demo-model"})
                return {
                    "provider": pref["provider"],
                    "base_url": "http://local-dashboard-test",
                    "model": pref["model"],
                    "has_model_override": "yes",
                    "available_providers": "custom, openai",
                }

            def process_message(self, user_id: str, user_input: str) -> str:
                row = {
                    "id": f"J-{uuid4().hex[:8]}",
                    "status": "completed",
                    "created_ts": "1",
                    "completed_ts": "1",
                    "error": "",
                    "output_preview": f"echo:{user_input}",
                }
                self._jobs.setdefault(str(user_id), []).insert(0, row)
                return f"echo:{user_input}"

            def list_available_providers(self) -> list[str]:
                return ["custom", "openai"]

            def get_provider_status(self, user_id: str) -> dict[str, str]:
                return self._status(user_id)

            def set_provider_for_user(self, user_id: str, provider: str) -> tuple[bool, str]:
                self._prefs.setdefault(str(user_id), {"provider": "custom", "model": "demo-model"})["provider"] = provider
                return True, f"Provider set to `{provider}`."

            def set_model_for_user(self, user_id: str, model: str) -> tuple[bool, str]:
                self._prefs.setdefault(str(user_id), {"provider": "custom", "model": "demo-model"})["model"] = model
                return True, f"Model override set to `{model}`."

            def clear_model_override_for_user(self, user_id: str) -> tuple[bool, str]:
                self._prefs.setdefault(str(user_id), {"provider": "custom", "model": "demo-model"})["model"] = "demo-model"
                return True, "Model override cleared."

            def get_tool_policy_status(self, user_id: str) -> dict[str, str]:
                _ = user_id
                return {
                    "profile": "balanced",
                    "allow_tools": "demo_tool",
                    "deny_tools": "[none]",
                    "deny_permissions": "[none]",
                }

            def list_tool_profiles(self) -> list[str]:
                return ["balanced", "locked"]

            def usage_report(self, user_id: str) -> str:
                _ = user_id
                return "Usage Summary\n- LLM calls: 1\n- Tool calls: 0\n- Estimated LLM cost: $0.0000"

            def list_dynamic_skill_states(self) -> list[dict[str, str]]:
                return [
                    {
                        "tool_name": "demo_tool",
                        "folder": "demo",
                        "display_name": "Demo Skill",
                        "status": "enabled",
                        "permissions": "safe-read",
                        "runtime_mode": "python",
                    }
                ]

            def list_plugins(self) -> list[dict[str, str]]:
                return [
                    {
                        "name": "demo-plugin",
                        "source_type": "local",
                        "installed_at": "now",
                        "pin_ref": "[none]",
                        "enabled": "yes",
                        "skills": "demo",
                    }
                ]

            def list_session_jobs(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
                return self._jobs.get(str(user_id), [])[:limit]

            def resume_session_job(self, job_id: str) -> tuple[bool, str]:
                return True, f"Resumed job `{job_id}`."

        class FakeServiceManager:
            def status(self) -> tuple[bool, str]:
                return True, "demo-service up"

        app = create_dashboard_app(
            local_settings,
            orchestrator=FakeOrchestrator(manager),
            service_manager=FakeServiceManager(),
        )
        client = TestClient(app)
        health = client.get("/api/health")
        sessions = client.get("/api/chat/sessions")
        if sessions.status_code != 200:
            return False, "Dashboard session listing endpoint failed."
        sessions_payload = sessions.json()
        session_id = str(sessions_payload.get("default_session_id", "")).strip()
        if not session_id:
            return False, "Dashboard did not create a default session."
        created = client.post("/api/chat/sessions", json={"title": "Parity Session"})
        if created.status_code != 200:
            return False, "Dashboard session creation endpoint failed."
        created_session_id = str(created.json().get("session", {}).get("id", "")).strip()
        if not created_session_id:
            return False, "Created dashboard session is missing an id."
        transcript = client.post(
            f"/api/chat/sessions/{created_session_id}/messages",
            json={"text": "hello from parity"},
        )
        provider = client.post(
            f"/api/chat/sessions/{created_session_id}/provider",
            json={"provider": "openai"},
        )
        model = client.post(
            f"/api/chat/sessions/{created_session_id}/model",
            json={"model": "gpt-demo"},
        )
        pending = client.get("/api/approvals/pending")
        approve = client.post(f"/api/approvals/{record.id}/approve", json={"actor": "parity-suite"})
        record2 = manager.request_approval(
            action_type="file_write",
            payload={"path": "doc.md"},
            requested_by="parity-user",
            reason="dashboard deny parity",
        )
        deny = client.post(
            f"/api/approvals/{record2.id}/deny",
            json={"actor": "parity-suite", "reason": "policy block"},
        )
        skills = client.get("/api/skills")
        plugins = client.get("/api/plugins")
        config = client.get("/api/config")
        if health.status_code != 200:
            return False, "Dashboard health endpoint failed."
        if transcript.status_code != 200 or len(transcript.json().get("messages", [])) < 2:
            return False, "Dashboard direct chat endpoint failed."
        if provider.status_code != 200 or not bool(provider.json().get("ok")):
            return False, "Dashboard provider update endpoint failed."
        if model.status_code != 200 or not bool(model.json().get("ok")):
            return False, "Dashboard model update endpoint failed."
        if pending.status_code != 200:
            return False, "Dashboard pending approvals endpoint failed."
        if approve.status_code != 200 or not bool(approve.json().get("ok")):
            return False, "Dashboard approve action failed."
        if deny.status_code != 200 or not bool(deny.json().get("ok")):
            return False, "Dashboard deny action failed."
        if skills.status_code != 200 or plugins.status_code != 200 or config.status_code != 200:
            return False, "Dashboard support endpoints failed."
        return True, "Dashboard API control-panel flow passed."

    run_check("install_scripts", True, check_install_scripts)
    run_check("workspace_scaffold", True, check_workspace_scaffold)
    run_check("doctor_critical", True, check_doctor_runtime)
    run_check("adapter_modules", True, check_adapter_modules)
    run_check("skill_loader", True, check_skill_loader)
    run_check("plugin_registry", True, check_plugin_registry)
    run_check("approval_lifecycle", True, check_approval_lifecycle)
    run_check("safe_shell_gate", True, check_safe_shell_gate)
    run_check("session_engine", True, check_session_engine)
    run_check("external_approvals_tcp", True, check_external_approvals_tcp)
    run_check("dashboard_api", True, check_dashboard_api)

    passed = len([item for item in results if item.ok])
    failed_required = [item for item in results if (not item.ok and item.required)]
    failed_optional = [item for item in results if (not item.ok and not item.required)]
    total = len(results)
    summary = {
        "passed": passed,
        "failed_required": len(failed_required),
        "failed_optional": len(failed_optional),
        "total": total,
        "strict": strict,
    }
    exit_code = 0 if not failed_required and (not strict or not failed_optional) else 1
    return exit_code, results, summary


def run_parity_cli(settings: Settings, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent1 parity", description="Run OpenClaw parity capability checks.")
    parser.add_argument("--strict", action="store_true", help="Fail on optional warnings too.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--output", default="", help="Optional output path for JSON report.")
    args = parser.parse_args(argv)

    exit_code, results, summary = run_parity_check(settings=settings, strict=args.strict)
    payload = {
        "summary": summary,
        "results": [asdict(item) for item in results],
    }

    if args.output.strip():
        output_path = Path(os.path.expandvars(os.path.expanduser(args.output.strip())))
        if not output_path.is_absolute():
            output_path = (PROJECT_ROOT / output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
        return exit_code

    print("Agent 1 Parity Report")
    for row in results:
        status = "PASS" if row.ok else "FAIL"
        req = "required" if row.required else "optional"
        print(f"- [{status}] {row.name} ({req}) {row.duration_ms}ms: {row.details}")
    print(
        "Summary: "
        f"{summary['passed']}/{summary['total']} passed | "
        f"required_failures={summary['failed_required']} | optional_failures={summary['failed_optional']}"
    )
    if args.output.strip():
        print(f"Report written: {args.output}")
    return exit_code
