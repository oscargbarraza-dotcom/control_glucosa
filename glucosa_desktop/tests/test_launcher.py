import socket

import pytest

from glucosa.__main__ import ENV_ACCESS_TOKEN, build_command, build_plan, free_port


def option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


def option_values(command: list[str], name: str) -> list[str]:
    """Opciones multivalor de Streamlit: se repite la bandera, no se separa con comas."""
    return [command[i + 1] for i, token in enumerate(command) if token == name]


def test_launcher_enforces_security_options_without_relying_on_the_working_directory():
    command = build_command(8765)

    assert option(command, "--server.address") == "127.0.0.1"
    assert option(command, "--server.port") == "8765"
    assert option(command, "--server.headless") == "true"
    assert option(command, "--server.enableCORS") == "true"
    assert option(command, "--server.enableXsrfProtection") == "true"
    assert option_values(command, "--server.allowedHosts") == ["127.0.0.1", "localhost"]
    assert option(command, "--server.maxUploadSize") == "30"
    assert option(command, "--server.enableStaticServing") == "false"
    assert option(command, "--global.developmentMode") == "false"
    assert option(command, "--client.showErrorDetails") == "none"
    assert option(command, "--client.disableDataExport") == "true"
    assert option(command, "--browser.gatherUsageStats") == "false"
    assert option(command, "--theme.base") == "dark"
    assert option(command, "--theme.primaryColor") == "#6B7A8F"


def test_launcher_runs_the_streamlit_app_module():
    command = build_command(8765)
    assert command[1:4] == ["-m", "streamlit", "run"]
    assert command[4].endswith("app.py")


def test_free_port_is_a_loopback_port_that_can_be_bound():
    port = free_port()

    assert 1024 <= port <= 65535
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))


def test_each_launch_gets_a_new_random_port_and_a_long_random_token():
    plans = [build_plan(environ={}) for _ in range(5)]

    tokens = {p.env[ENV_ACCESS_TOKEN] for p in plans}
    assert len(tokens) == 5
    assert all(len(token) >= 40 for token in tokens)


def test_the_token_reaches_the_server_only_through_its_environment_not_its_command_line():
    plan = build_plan(environ={"PATH": "x"})
    token = plan.env[ENV_ACCESS_TOKEN]

    assert token not in " ".join(plan.command)
    assert plan.env["PATH"] == "x"  # el entorno del usuario se conserva


def test_the_browser_url_is_loopback_and_carries_the_token_of_that_launch():
    plan = build_plan(environ={}, port=9123, token="T" * 43)

    assert plan.url == "http://127.0.0.1:9123/?t=" + "T" * 43
    assert option(plan.command, "--server.port") == "9123"


def test_a_token_inherited_from_the_environment_is_never_reused():
    plan = build_plan(environ={ENV_ACCESS_TOKEN: "viejo-token-heredado"})

    assert plan.env[ENV_ACCESS_TOKEN] != "viejo-token-heredado"


@pytest.mark.parametrize("bad", [0, -1, 70000])
def test_invalid_ports_are_rejected(bad):
    with pytest.raises(ValueError):
        build_command(bad)


class FakeServer:
    pid = 4321

    def __init__(self):
        self.terminated = False
        self.waited = False
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        self.waited = True
        self._alive = False

    def kill(self):
        self._alive = False


def test_on_windows_closing_the_launcher_kills_the_whole_server_process_tree(monkeypatch):
    import glucosa.__main__ as launcher

    calls = []
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kw: calls.append(args))
    server = FakeServer()

    launcher._stop(server)

    assert calls == [["taskkill", "/PID", "4321", "/T", "/F"]]  # el venv lanza un proceso hijo
    assert server.waited


def test_on_other_systems_the_server_is_terminated_normally(monkeypatch):
    import glucosa.__main__ as launcher

    monkeypatch.setattr(launcher.sys, "platform", "linux")
    server = FakeServer()

    launcher._stop(server)

    assert server.terminated and server.waited


def test_stopping_an_already_finished_server_does_nothing():
    import glucosa.__main__ as launcher

    server = FakeServer()
    server._alive = False

    launcher._stop(server)

    assert not server.terminated and not server.waited
