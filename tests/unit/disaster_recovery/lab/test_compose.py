import subprocess
from unittest.mock import patch

from infraguard.modules.disaster_recovery.lab import compose


def _ok(args, **kwargs):
    return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")


def _fail(args, **kwargs):
    return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="not found")


def test_prefers_docker_compose_plugin_when_available() -> None:
    compose.compose_base_command.cache_clear()
    with patch("shutil.which", return_value="/usr/bin/docker"), patch(
        "subprocess.run", side_effect=_ok
    ):
        assert compose.compose_base_command() == ("docker", "compose")
    compose.compose_base_command.cache_clear()


def test_falls_back_to_standalone_docker_compose() -> None:
    compose.compose_base_command.cache_clear()

    def which(name, *a, **kw):
        return "/usr/local/bin/docker-compose" if name == "docker-compose" else None

    def run(args, **kwargs):
        if args[:2] == ["docker", "compose"]:
            return _fail(args)
        return _ok(args)

    with patch("shutil.which", side_effect=which), patch("subprocess.run", side_effect=run):
        assert compose.compose_base_command() == ("docker-compose",)
    compose.compose_base_command.cache_clear()


def test_raises_when_neither_is_available() -> None:
    compose.compose_base_command.cache_clear()
    with (
        patch("shutil.which", return_value=None),
        patch("subprocess.run", side_effect=_fail),
    ):
        try:
            compose.compose_base_command()
            raised = False
        except compose.LabUnavailableError:
            raised = True
    assert raised
    compose.compose_base_command.cache_clear()
