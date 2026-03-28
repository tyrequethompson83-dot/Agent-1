from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from agent1.approvals_bridge import ExternalApprovalsBridge
from agent1.config import Settings
from agent1.migrations import MigrationManager
from agent1.provider_router import ProviderRouter


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str
    fix: str = ""


class Doctor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers = ProviderRouter(settings)
        self.external_bridge = ExternalApprovalsBridge(settings)

    def _check_python(self) -> CheckResult:
        ok = sys.version_info >= (3, 11)
        return CheckResult(
            name="python_version",
            ok=ok,
            details=f"Detected {sys.version.split()[0]} (requires >= 3.11).",
        )

    def _check_paths(self) -> CheckResult:
        required: list[Path] = [
            self.settings.data_dir,
            self.settings.workspace_profile_path,
            self.settings.skills_root_path,
            self.settings.plugins_root_path,
            self.settings.markdown_memory_path,
            self.settings.vector_memory_path,
            self.settings.app_log_path.parent,
            self.settings.safe_files_root,
            self.settings.session_jobs_path.parent,
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            return CheckResult("paths", False, "Missing paths: " + ", ".join(missing), "Run `agent1 doctor_fix`.")
        return CheckResult("paths", True, "All required runtime paths exist.")

    def _check_provider_profiles(self) -> CheckResult:
        available = self.providers.list_available_provider_names()
        if not available:
            return CheckResult(
                "providers",
                False,
                "No provider profile is fully configured.",
                "Set API key/base URL/model in .env or run `agent1 init`.",
            )
        return CheckResult("providers", True, "Available providers: " + ", ".join(available))

    def _check_telegram(self) -> CheckResult:
        if self.settings.chat_adapter.strip().lower() != "telegram":
            return CheckResult("telegram", True, "Telegram adapter not selected.")
        if self.settings.telegram_bot_token.strip():
            return CheckResult("telegram", True, "TELEGRAM_BOT_TOKEN is set.")
        return CheckResult("telegram", False, "TELEGRAM_BOT_TOKEN is empty (CLI-only mode).", "Set TELEGRAM_BOT_TOKEN in .env.")

    def _check_discord(self) -> CheckResult:
        if self.settings.chat_adapter.strip().lower() != "discord":
            return CheckResult("discord", True, "Discord adapter not selected.")
        if self.settings.discord_bot_token.strip():
            return CheckResult("discord", True, "DISCORD_BOT_TOKEN is set.")
        return CheckResult("discord", False, "CHAT_ADAPTER=discord but DISCORD_BOT_TOKEN is empty.", "Set DISCORD_BOT_TOKEN in .env.")

    def _check_slack(self) -> CheckResult:
        if self.settings.chat_adapter.strip().lower() != "slack":
            return CheckResult("slack", True, "Slack adapter not selected.")
        if not self.settings.slack_bot_token.strip() or not self.settings.slack_app_token.strip():
            return CheckResult(
                "slack",
                False,
                "CHAT_ADAPTER=slack but SLACK_BOT_TOKEN or SLACK_APP_TOKEN is empty.",
                "Set both Slack tokens in .env.",
            )
        installed = importlib.util.find_spec("slack_bolt") is not None
        if not installed:
            return CheckResult("slack", False, "slack_bolt module is missing.", "Install dependency: pip install slack_bolt")
        return CheckResult("slack", True, "Slack tokens and module are configured.")

    def _check_whatsapp(self) -> CheckResult:
        if self.settings.chat_adapter.strip().lower() != "whatsapp":
            return CheckResult("whatsapp", True, "WhatsApp adapter not selected.")
        missing: list[str] = []
        if not self.settings.whatsapp_verify_token.strip():
            missing.append("WHATSAPP_VERIFY_TOKEN")
        if not self.settings.whatsapp_access_token.strip():
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not self.settings.whatsapp_phone_number_id.strip():
            missing.append("WHATSAPP_PHONE_NUMBER_ID")
        if missing:
            return CheckResult(
                "whatsapp",
                False,
                "CHAT_ADAPTER=whatsapp but required settings are missing: " + ", ".join(missing),
                "Set WhatsApp Cloud API credentials in .env.",
            )
        fastapi_installed = importlib.util.find_spec("fastapi") is not None
        uvicorn_installed = importlib.util.find_spec("uvicorn") is not None
        if not fastapi_installed or not uvicorn_installed:
            return CheckResult(
                "whatsapp",
                False,
                "WhatsApp webhook dependencies missing (fastapi/uvicorn).",
                "Install dependencies: pip install fastapi uvicorn",
            )
        return CheckResult(
            "whatsapp",
            True,
            f"WhatsApp adapter configured on {self.settings.whatsapp_host}:{self.settings.whatsapp_port}.",
        )

    def _check_bridge(self) -> CheckResult:
        if self.settings.chat_adapter.strip().lower() != "bridge":
            return CheckResult("bridge", True, "Bridge adapter not selected.")
        if int(self.settings.bridge_port) <= 0:
            return CheckResult("bridge", False, "BRIDGE_PORT must be > 0.", "Set BRIDGE_PORT in .env.")
        fastapi_installed = importlib.util.find_spec("fastapi") is not None
        uvicorn_installed = importlib.util.find_spec("uvicorn") is not None
        if not fastapi_installed or not uvicorn_installed:
            return CheckResult(
                "bridge",
                False,
                "Bridge dependencies missing (fastapi/uvicorn).",
                "Install dependencies: pip install fastapi uvicorn",
            )
        if not self.settings.bridge_auth_token.strip():
            return CheckResult(
                "bridge",
                False,
                "BRIDGE_AUTH_TOKEN is empty; webhook would be unauthenticated.",
                "Set BRIDGE_AUTH_TOKEN in .env.",
            )
        return CheckResult(
            "bridge",
            True,
            f"Bridge is configured on {self.settings.bridge_host}:{self.settings.bridge_port}.",
        )

    def _check_playwright(self) -> CheckResult:
        installed = importlib.util.find_spec("playwright") is not None
        if installed:
            return CheckResult("playwright_module", True, "playwright module is installed.")
        return CheckResult("playwright_module", False, "playwright module is missing.", "Install dependency: pip install playwright")

    def _check_skills(self) -> CheckResult:
        count = len([p for p in self.settings.skills_root_path.iterdir() if p.is_dir()]) if self.settings.skills_root_path.exists() else 0
        return CheckResult("skills_dir", True, f"Found {count} skill directories.")

    def _check_plugins(self) -> CheckResult:
        exists = self.settings.plugins_registry_path.exists()
        return CheckResult(
            "plugins_registry",
            exists,
            f"Plugins registry: {self.settings.plugins_registry_path}" if exists else "Plugins registry missing.",
            "" if exists else "Run `agent1 doctor_fix` to recreate registry files.",
        )

    def _check_external_approvals(self) -> CheckResult:
        if not self.settings.external_approvals_enabled:
            return CheckResult("external_approvals", True, "External approvals bridge disabled (local approvals active).")
        exists = self.settings.external_approvals_config_path.exists()
        if not exists:
            return CheckResult(
                "external_approvals",
                False,
                f"Missing config: {self.settings.external_approvals_config_path}",
                "Set EXTERNAL_APPROVALS_CONFIG_PATH to your daemon config file.",
            )
        reachable, details = self.external_bridge.socket_reachable()
        return CheckResult("external_approvals", reachable, details, "" if reachable else "Check daemon socket path/token.")

    def _check_email_auth(self) -> CheckResult:
        if not self.settings.email_enabled:
            return CheckResult("email_auth", True, "Email integration disabled.")
        if not (self.settings.email_address.strip() and self.settings.email_password.strip()):
            return CheckResult(
                "email_auth",
                False,
                "EMAIL_ENABLED=true but EMAIL_ADDRESS or EMAIL_PASSWORD is missing.",
                "Set email credentials (prefer app password).",
            )
        return CheckResult("email_auth", True, "Email credentials are configured.")

    def _check_calendar_auth(self) -> CheckResult:
        if not self.settings.calendar_enabled:
            return CheckResult("calendar_auth", True, "Calendar integration disabled.")
        creds = self.settings.google_calendar_credentials_path
        token = self.settings.google_calendar_token_path
        if not creds.exists():
            return CheckResult(
                "calendar_auth",
                False,
                f"Google credentials missing: {creds}",
                "Run scripts/setup_google_calendar.py after adding credentials json.",
            )
        if not token.exists():
            return CheckResult(
                "calendar_auth",
                False,
                f"Google token missing: {token}",
                "Run scripts/setup_google_calendar.py to generate token.",
            )
        return CheckResult("calendar_auth", True, "Calendar credentials/token are present.")

    def run(self) -> list[CheckResult]:
        return [
            self._check_python(),
            self._check_paths(),
            self._check_provider_profiles(),
            self._check_telegram(),
            self._check_discord(),
            self._check_slack(),
            self._check_whatsapp(),
            self._check_bridge(),
            self._check_playwright(),
            self._check_skills(),
            self._check_plugins(),
            self._check_external_approvals(),
            self._check_email_auth(),
            self._check_calendar_auth(),
        ]

    def apply_quick_fixes(self) -> str:
        self.settings.ensure_paths()
        migration = MigrationManager(self.settings)
        migration_result = migration.migrate()
        return "Applied quick fixes:\n- ensured runtime directories\n- " + migration_result

    def report_text(self) -> str:
        results = self.run()
        lines = ["Agent 1 Doctor Report"]
        failed = 0
        for result in results:
            status = "OK" if result.ok else "FAIL"
            if not result.ok:
                failed += 1
            lines.append(f"- [{status}] {result.name}: {result.details}")
            if result.fix and not result.ok:
                lines.append(f"  fix: {result.fix}")
        lines.append(f"Summary: {len(results) - failed}/{len(results)} checks passed.")
        return "\n".join(lines)
