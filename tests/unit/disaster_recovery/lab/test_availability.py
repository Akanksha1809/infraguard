import subprocess
from unittest.mock import patch

from infraguard.modules.disaster_recovery.lab.availability import check_lab_available


def test_unavailable_when_docker_cli_missing() -> None:
    with patch("shutil.which", return_value=None):
        result = check_lab_available()
    assert result.available is False
    assert "docker" in result.reason.lower()


def test_unavailable_when_daemon_unreachable() -> None:
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="daemon down")

    with patch("shutil.which", return_value="/usr/bin/docker"), patch("subprocess.run", side_effect=run):
        result = check_lab_available()
    assert result.available is False
    assert "daemon" in result.reason.lower()


def test_available_when_docker_and_compose_work() -> None:
    from infraguard.modules.disaster_recovery.lab import compose

    compose.compose_base_command.cache_clear()

    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    with patch("shutil.which", return_value="/usr/bin/docker"), patch("subprocess.run", side_effect=run):
        result = check_lab_available()
    compose.compose_base_command.cache_clear()
    assert result.available is True
    assert result.reason is None
