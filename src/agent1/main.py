from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING

from agent1.cli.init import run_init_walkthrough
from agent1.cli.onboard import run_onboard
from agent1.config import get_settings
from agent1.logging_setup import configure_logging
from agent1.migrations import MigrationManager
from agent1.service_manager import ServiceManager

if TYPE_CHECKING:
    from agent1.agents.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


def _run_gateway_command(service: ServiceManager, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agent1 gateway", description="Gateway/service lifecycle helpers.")
    parser.add_argument("action", nargs="?", choices=["up", "down", "status"], default="status")
    parser.add_argument("--no-build", action="store_true", help="Skip docker image rebuild on `up`.")
    args = parser.parse_args(argv)

    if args.action == "up":
        ok, message = service.up(build=not args.no_build)
    elif args.action == "down":
        ok, message = service.down()
    else:
        ok, message = service.status()
    print(message if ok else f"Error: {message}")
    return 0 if ok else 1


def _run_dashboard_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="agent1 dashboard", description="Run local Agent 1 dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    from agent1.dashboard import run_dashboard

    settings = get_settings()
    run_dashboard(settings=settings, host=args.host, port=args.port)
    return 0


def _run_approvals_command(argv: list[str]) -> int:
    from agent1.cli.approvals import run_approvals_cli

    settings = get_settings()
    return run_approvals_cli(settings=settings, argv=argv)


def _run_parity_command(argv: list[str]) -> int:
    from agent1.cli.parity import run_parity_cli

    settings = get_settings()
    return run_parity_cli(settings=settings, argv=argv)


def run_cli_mode(orchestrator: AgentOrchestrator) -> None:
    print("Agent 1 CLI mode. Type 'exit' to quit.")
    print(
        "CLI commands: /providers, /provider <name>, /model <name|default>, /profile, /skills, "
        "/skill_enable <folder>, /skill_disable <folder>, /plugins, /plugin_install <source> [name] [ref], "
        "/plugin_update <name>, /plugin_uninstall <name>, /plugin_pin <name> <ref|clear>, "
        "/plugin_enable <name>, /plugin_disable <name>, /policy, /policy_set <profile>, "
        "/policy_tool <allow|deny|clear> <tool>, /policy_permission <allow|deny|clear> <permission>, "
        "/policy_reset, /jobs, /resume_job <job_id>, /usage, /doctor, /doctor_fix, /up, /down, /upgrade, "
        "/approve <id>, /deny <id> [reason], /pending"
    )
    user_id = "local-cli-user"
    while True:
        try:
            text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if text.lower() in {"exit", "quit"}:
            print("Exiting.")
            return
        if not text:
            continue

        if text.startswith("/providers"):
            providers = orchestrator.list_available_providers()
            print("Providers:", ", ".join(providers) if providers else "[none configured]")
            continue

        if text.startswith("/provider"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                status = orchestrator.get_provider_status(user_id)
                print(f"Provider={status['provider']} Model={status['model']} URL={status['base_url']}")
            else:
                ok, message = orchestrator.set_provider_for_user(user_id, parts[1])
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/model"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                status = orchestrator.get_provider_status(user_id)
                print(f"Model={status['model']} Override={status['has_model_override']}")
            else:
                value = parts[1].strip()
                if value.lower() in {"default", "clear", "reset"}:
                    ok, message = orchestrator.clear_model_override_for_user(user_id)
                else:
                    ok, message = orchestrator.set_model_for_user(user_id, value)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/profile"):
            status = orchestrator.get_provider_status(user_id)
            print(
                f"Provider={status['provider']} | Model={status['model']} | URL={status['base_url']} | "
                f"Override={status['has_model_override']}"
            )
            continue

        if text.startswith("/skills"):
            rows = orchestrator.list_dynamic_skill_states()
            if not rows:
                print("Dynamic skills: [none loaded]")
            else:
                for row in rows:
                    print(f"- {row['folder']} ({row['status']}) runtime={row['runtime_mode']} -> {row['tool_name']}")
            continue

        if text.startswith("/skill_enable"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print("Usage: /skill_enable <folder_name>")
            else:
                ok, message = orchestrator.set_skill_enabled(parts[1].strip(), enabled=True)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/skill_disable"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print("Usage: /skill_disable <folder_name>")
            else:
                ok, message = orchestrator.set_skill_enabled(parts[1].strip(), enabled=False)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/policy_set"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print("Usage: /policy_set <full|safe|messaging>")
            else:
                ok, message = orchestrator.set_tool_profile_for_user(user_id, parts[1].strip())
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/policy_tool"):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /policy_tool <allow|deny|clear> <tool_name>")
            else:
                mode, tool_name = parts[1].strip(), parts[2].strip()
                ok, message = orchestrator.set_tool_override(user_id=user_id, mode=mode, tool_name=tool_name)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/policy_permission"):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /policy_permission <allow|deny|clear> <permission>")
            else:
                mode, permission = parts[1].strip(), parts[2].strip()
                ok, message = orchestrator.set_permission_override(user_id=user_id, mode=mode, permission=permission)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/policy_reset"):
            ok, message = orchestrator.clear_policy_overrides(user_id=user_id)
            print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/doctor_fix"):
            fixes = orchestrator.doctor.apply_quick_fixes()
            print(fixes)
            print(orchestrator.doctor_report())
            continue

        if text.startswith("/approve"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /approve <approval_id>")
            else:
                ok, message = orchestrator.approvals.approve(approval_id=parts[1].strip(), approved_by=user_id)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/deny"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                print("Usage: /deny <approval_id> [reason]")
            else:
                approval_id = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else ""
                ok, message = orchestrator.approvals.deny(approval_id=approval_id, denied_by=user_id, reason=reason)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/pending"):
            rows = orchestrator.approvals.list_pending(limit=15)
            if not rows:
                print("No pending approvals.")
            else:
                for row in rows:
                    print(f"- {row.id} | {row.action_type} | {row.reason}")
            continue

        if text.startswith("/policy"):
            status = orchestrator.get_tool_policy_status(user_id)
            print(
                f"Profile={status['profile']} | Allowed tools={status['allow_tools']} | Denied tools={status['deny_tools']} | "
                f"Denied permissions={status['deny_permissions']}"
            )
            continue

        if text.startswith("/doctor"):
            print(orchestrator.doctor_report())
            continue

        if text.startswith("/usage"):
            print(orchestrator.usage_report(user_id=user_id))
            continue

        if text.startswith("/plugins"):
            rows = orchestrator.list_plugins()
            if not rows:
                print("No plugins installed.")
            else:
                for row in rows:
                    print(
                        f"- {row['name']} [{row['source_type']}] enabled={row['enabled']} "
                        f"pin={row['pin_ref']} skills={row['skills']}"
                    )
            continue

        if text.startswith("/plugin_install"):
            parts = text.split(maxsplit=3)
            if len(parts) < 2:
                print("Usage: /plugin_install <source> [name] [ref]")
            else:
                source = parts[1]
                name = parts[2] if len(parts) > 2 else ""
                ref = parts[3] if len(parts) > 3 else ""
                ok, message = orchestrator.install_plugin(source=source, name=name, ref=ref)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/plugin_update"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print("Usage: /plugin_update <name>")
            else:
                ok, message = orchestrator.update_plugin(parts[1].strip())
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/plugin_uninstall"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                print("Usage: /plugin_uninstall <name>")
            else:
                ok, message = orchestrator.uninstall_plugin(parts[1].strip())
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/plugin_pin"):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /plugin_pin <name> <ref|clear>")
            else:
                name = parts[1].strip()
                ref = parts[2].strip()
                if ref.lower() in {"clear", "none", "unset"}:
                    ref = ""
                ok, message = orchestrator.set_plugin_pin(name=name, ref=ref)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/plugin_enable"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /plugin_enable <name>")
            else:
                ok, message = orchestrator.set_plugin_enabled(name=parts[1].strip(), enabled=True)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/plugin_disable"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /plugin_disable <name>")
            else:
                ok, message = orchestrator.set_plugin_enabled(name=parts[1].strip(), enabled=False)
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/jobs"):
            rows = orchestrator.list_session_jobs(user_id=user_id, limit=12)
            if not rows:
                print("No recent jobs.")
            else:
                for row in rows:
                    print(f"- {row['id']} [{row['status']}] created={row['created_ts']} error={row['error'] or '[none]'}")
            continue

        if text.startswith("/resume_job"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /resume_job <job_id>")
            else:
                ok, message = orchestrator.resume_session_job(parts[1].strip())
                print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/up"):
            ok, message = ServiceManager().up(build=True)
            print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/down"):
            ok, message = ServiceManager().down()
            print(message if ok else f"Error: {message}")
            continue

        if text.startswith("/upgrade"):
            print(MigrationManager(orchestrator.settings).migrate())
            continue

        response = orchestrator.process_message(user_id=user_id, user_input=text)
        print(f"\nAgent 1> {response}")


def run() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--style", dest="init_style", choices=["home", "project"], default=None)
    parser.add_argument("--home-path", dest="init_home_path", default=None)
    args, _unknown = parser.parse_known_args(sys.argv[1:])

    if args.command == "init":
        run_init_walkthrough(default_style=args.init_style, default_home_path=args.init_home_path)
        return
    if args.command == "onboard":
        code = run_onboard(
            argv=_unknown,
            default_style=args.init_style,
            default_home_path=args.init_home_path,
        )
        if code:
            raise SystemExit(code)
        return
    if args.command == "dashboard":
        code = _run_dashboard_command(_unknown)
        if code:
            raise SystemExit(code)
        return

    settings = get_settings()
    configure_logging(settings)
    service = ServiceManager()

    if args.command == "approvals":
        code = _run_approvals_command(_unknown)
        if code:
            raise SystemExit(code)
        return
    if args.command == "parity":
        code = _run_parity_command(_unknown)
        if code:
            raise SystemExit(code)
        return
    if args.command in {"gateway", "daemon"}:
        code = _run_gateway_command(service=service, argv=_unknown)
        if code:
            raise SystemExit(code)
        return
    if args.command == "status":
        ok, message = service.status()
        print(message if ok else f"Error: {message}")
        if not ok:
            raise SystemExit(1)
        return

    if args.command == "doctor":
        from agent1.diagnostics import Doctor

        print(Doctor(settings).report_text())
        return
    if args.command == "doctor_fix":
        from agent1.diagnostics import Doctor

        doctor = Doctor(settings)
        print(doctor.apply_quick_fixes())
        print(doctor.report_text())
        return
    if args.command == "up":
        ok, message = service.up(build=True)
        print(message if ok else f"Error: {message}")
        return
    if args.command == "down":
        ok, message = service.down()
        print(message if ok else f"Error: {message}")
        return
    if args.command == "upgrade":
        print(MigrationManager(settings).migrate())
        return

    from agent1.agents.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator(settings)
    if args.command == "plugins":
        rows = orchestrator.list_plugins()
        if not rows:
            print("No plugins installed.")
        else:
            for row in rows:
                print(
                    f"- {row['name']} [{row['source_type']}] enabled={row['enabled']} "
                    f"pin={row['pin_ref']} skills={row['skills']}"
                )
        return

    adapter_mode = settings.chat_adapter.strip().lower()
    if adapter_mode == "discord":
        if settings.discord_bot_token.strip():
            logger.info("Starting Agent 1 in Discord mode.")
            from agent1.integrations.discord_bot import DiscordBotAdapter

            adapter = DiscordBotAdapter(settings=settings, orchestrator=orchestrator)
            adapter.run()
            return
        logger.info("CHAT_ADAPTER=discord but DISCORD_BOT_TOKEN is empty; falling back to CLI mode.")
    elif adapter_mode == "slack":
        if settings.slack_bot_token.strip() and settings.slack_app_token.strip():
            logger.info("Starting Agent 1 in Slack mode.")
            from agent1.integrations.slack_bot import SlackBotAdapter

            adapter = SlackBotAdapter(settings=settings, orchestrator=orchestrator)
            adapter.run()
            return
        logger.info("CHAT_ADAPTER=slack but SLACK_BOT_TOKEN/SLACK_APP_TOKEN are missing; falling back to CLI mode.")
    elif adapter_mode == "bridge":
        logger.info("Starting Agent 1 in Bridge mode on %s:%s.", settings.bridge_host, settings.bridge_port)
        from agent1.integrations.bridge_webhook import BridgeWebhookAdapter

        adapter = BridgeWebhookAdapter(settings=settings, orchestrator=orchestrator)
        adapter.run()
        return
    elif adapter_mode == "whatsapp":
        if (
            settings.whatsapp_verify_token.strip()
            and settings.whatsapp_access_token.strip()
            and settings.whatsapp_phone_number_id.strip()
        ):
            logger.info(
                "Starting Agent 1 in WhatsApp mode on %s:%s.",
                settings.whatsapp_host,
                settings.whatsapp_port,
            )
            from agent1.integrations.whatsapp_bot import WhatsAppAdapter

            adapter = WhatsAppAdapter(settings=settings, orchestrator=orchestrator)
            adapter.run()
            return
        logger.info(
            "CHAT_ADAPTER=whatsapp but WHATSAPP_VERIFY_TOKEN/WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID are missing; "
            "falling back to CLI mode."
        )
    elif adapter_mode == "telegram":
        if settings.telegram_bot_token.strip():
            logger.info("Starting Agent 1 in Telegram mode.")
            from agent1.integrations.telegram_bot import TelegramBotAdapter

            adapter = TelegramBotAdapter(settings=settings, orchestrator=orchestrator)
            adapter.run()
            return
        logger.info("CHAT_ADAPTER=telegram but TELEGRAM_BOT_TOKEN is empty; falling back to CLI mode.")
    elif adapter_mode != "cli":
        logger.info("Unknown CHAT_ADAPTER=%s. Falling back to CLI mode.", adapter_mode)

    run_cli_mode(orchestrator)


if __name__ == "__main__":
    run()
