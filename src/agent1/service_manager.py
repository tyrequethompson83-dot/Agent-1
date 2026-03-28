from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from agent1.config import PROJECT_ROOT


class ServiceManager:
    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or PROJECT_ROOT

    @staticmethod
    def _docker_compose_base() -> list[str]:
        if shutil.which("docker"):
            return ["docker", "compose"]
        return []

    def up(self, build: bool = True) -> tuple[bool, str]:
        base = self._docker_compose_base()
        if not base:
            return False, "Docker is not available in PATH."
        command = [*base, "up", "-d"]
        if build:
            command.append("--build")
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
        except Exception as exc:
            return False, f"Failed running docker compose up: {exc}"
        if completed.returncode != 0:
            return False, (completed.stderr or completed.stdout or "docker compose up failed").strip()
        return True, (completed.stdout or "Services started.").strip()

    def down(self) -> tuple[bool, str]:
        base = self._docker_compose_base()
        if not base:
            return False, "Docker is not available in PATH."
        command = [*base, "down"]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        except Exception as exc:
            return False, f"Failed running docker compose down: {exc}"
        if completed.returncode != 0:
            return False, (completed.stderr or completed.stdout or "docker compose down failed").strip()
        return True, (completed.stdout or "Services stopped.").strip()

    def status(self) -> tuple[bool, str]:
        base = self._docker_compose_base()
        if not base:
            return False, "Docker is not available in PATH."
        command = [*base, "ps"]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except Exception as exc:
            return False, f"Failed running docker compose ps: {exc}"
        if completed.returncode != 0:
            return False, (completed.stderr or completed.stdout or "docker compose ps failed").strip()
        output = (completed.stdout or "").strip()
        if not output:
            output = "No services found."
        return True, output
