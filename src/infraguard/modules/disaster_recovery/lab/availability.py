"""Check whether the local recovery lab can run at all, so the CLI/API can explain the gap
plainly instead of failing with a raw stack trace — per the project's "explain which
optional capabilities are unavailable" requirement.
"""

import shutil
import subprocess
from dataclasses import dataclass

from infraguard.modules.disaster_recovery.lab.compose import LabUnavailableError, compose_base_command


@dataclass
class LabAvailability:
    available: bool
    reason: str | None = None


def check_lab_available() -> LabAvailability:
    if shutil.which("docker") is None:
        return LabAvailability(False, "The 'docker' CLI was not found on PATH.")
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return LabAvailability(False, f"Could not run 'docker info': {exc}")
    if result.returncode != 0:
        return LabAvailability(
            False, "The 'docker' CLI is installed but its daemon is not reachable (is it running?)."
        )
    try:
        compose_base_command()
    except LabUnavailableError as exc:
        return LabAvailability(False, str(exc))
    return LabAvailability(True, None)
