from __future__ import annotations

import argparse

from agent1.cli.init import run_init_walkthrough
from agent1.config import get_settings
from agent1.diagnostics import Doctor
from agent1.migrations import MigrationManager
from agent1.service_manager import ServiceManager


def run_onboard(
    argv: list[str] | None = None,
    default_style: str | None = None,
    default_home_path: str | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="agent1 onboard",
        description="Guided first-run setup with optional doctor/service bootstrap.",
    )
    parser.add_argument("--style", choices=["home", "project"], default=default_style or "home")
    parser.add_argument("--home-path", default=default_home_path)
    parser.add_argument("--doctor-fix", action="store_true", help="Apply quick doctor fixes after setup.")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip doctor report output.")
    parser.add_argument("--up", action="store_true", help="Start docker services after setup.")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip migration step.")
    args = parser.parse_args(argv)

    run_init_walkthrough(default_style=args.style, default_home_path=args.home_path)

    # Refresh settings from updated .env after walkthrough.
    get_settings.cache_clear()
    settings = get_settings()

    if not args.skip_migrate:
        print(MigrationManager(settings).migrate())

    doctor = Doctor(settings)
    if args.doctor_fix:
        print(doctor.apply_quick_fixes())
    if not args.skip_doctor:
        print(doctor.report_text())

    if args.up:
        ok, message = ServiceManager().up(build=True)
        print(message if ok else f"Error: {message}")
        return 0 if ok else 1

    print("Onboarding complete. Start with: `agent1` (chat) or `agent1 dashboard` (local UI).")
    return 0
