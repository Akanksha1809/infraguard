"""A deliberately narrow wrapper around Docker Compose and `docker exec`.

Every function here is hard-scoped to the lab's own project name, compose file, and
container (see constants.py) — none of them accept a caller-supplied project, container,
or file path. This is what makes "never touch anything outside the lab" an enforced
property of the code, not just a documented intention.

`docker compose` (the v2 CLI plugin) and the standalone `docker-compose` binary are both
supported, since which one actually works varies by host (see docs/IMPLEMENTATION_STATUS.md
Milestone 0: this project's own dev machine needs the standalone fallback).
"""

import shutil
import subprocess
from functools import lru_cache

from infraguard.modules.disaster_recovery.lab.constants import (
    COMPOSE_FILE,
    CONTAINER_NAME,
    PROJECT_NAME,
    STARTUP_TIMEOUT_SECONDS,
)


class LabUnavailableError(RuntimeError):
    """Docker/Compose is not usable on this machine. Callers should treat the lab as an
    optional capability and explain this to the user rather than crash.
    """


@lru_cache(maxsize=1)
def compose_base_command() -> tuple[str, ...]:
    if shutil.which("docker") is not None:
        probe = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=10
        )
        if probe.returncode == 0:
            return ("docker", "compose")
    if shutil.which("docker-compose") is not None:
        probe = subprocess.run(["docker-compose", "version"], capture_output=True, text=True, timeout=10)
        if probe.returncode == 0:
            return ("docker-compose",)
    raise LabUnavailableError(
        "Neither the 'docker compose' plugin nor a standalone 'docker-compose' binary is "
        "available/working on this machine."
    )


def _run_compose(args: list[str], timeout: int = STARTUP_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    cmd = [*compose_base_command(), "-p", PROJECT_NAME, "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def up() -> None:
    result = _run_compose(["up", "-d", "--wait", "--wait-timeout", str(STARTUP_TIMEOUT_SECONDS)])
    if result.returncode != 0:
        raise LabUnavailableError(f"'docker compose up' failed:\n{result.stderr}")


def down(remove_volumes: bool = True) -> None:
    args = ["down", "--remove-orphans"]
    if remove_volumes:
        args.append("-v")
    result = _run_compose(args)
    if result.returncode != 0:
        raise LabUnavailableError(f"'docker compose down' failed:\n{result.stderr}")


def is_running() -> bool:
    result = _run_compose(["ps", "--status", "running", "--services"])
    return result.returncode == 0 and "postgres" in result.stdout.split()


def exec_in_container(
    cmd: list[str], stdin_bytes: bytes | None = None, timeout: int = 30
) -> subprocess.CompletedProcess:
    """Run `cmd` inside the lab's own Postgres container via `docker exec` — never any
    other container, since CONTAINER_NAME is fixed.
    """
    full_cmd = ["docker", "exec"]
    if stdin_bytes is not None:
        full_cmd.append("-i")
    full_cmd.append(CONTAINER_NAME)
    full_cmd.extend(cmd)
    return subprocess.run(full_cmd, input=stdin_bytes, capture_output=True, timeout=timeout)
