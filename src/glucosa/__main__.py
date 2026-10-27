"""``python -m glucosa``: lanza la interfaz solo en 127.0.0.1 (nunca expuesta a la red).

Las opciones de seguridad se pasan explícitamente en la línea de comandos: Streamlit
lee ``.streamlit/config.toml`` del directorio de trabajo, que puede no ser el del
proyecto.

Cada ejecución usa un puerto libre al azar y un **token de acceso** nuevo (ver ``ui/access.py``):
el token viaja al servidor por variable de entorno (no aparece en su línea de comandos) y al
navegador en la URL que abre este lanzador. Al cerrar el lanzador se detiene el servidor.
"""

import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from glucosa.access_config import ENV_ACCESS_TOKEN, URL_TOKEN_PARAM

HOST = "127.0.0.1"
# Mismo tema que .streamlit/config.toml (un test comprueba que no se desalinean).
THEME_OPTIONS = {
    "base": "dark",
    "primaryColor": "#6B7A8F",
    "backgroundColor": "#0E1117",
    "secondaryBackgroundColor": "#161B22",
    "textColor": "#E6EAF0",
    "font": "sans serif",
}
STARTUP_TIMEOUT_SECONDS = 60
_TOKEN_BYTES = 32


@dataclass(frozen=True)
class LaunchPlan:
    command: list[str]
    env: dict[str, str]
    url: str
    port: int


def free_port() -> int:
    """Un puerto libre de loopback elegido por el sistema operativo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def build_command(port: int) -> list[str]:
    if not 1024 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 1024 y 65535.")
    app_file = Path(__file__).parent / "ui" / "app.py"
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_file),
        "--server.address",
        HOST,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.enableCORS",
        "true",
        "--server.enableXsrfProtection",
        "true",
        # Opción multivalor: una bandera por host (una cadena con comas sería un único host).
        "--server.allowedHosts",
        "127.0.0.1",
        "--server.allowedHosts",
        "localhost",
        "--server.maxUploadSize",
        "30",
        "--server.enableStaticServing",
        "false",
        "--global.developmentMode",
        "false",
        "--client.showErrorDetails",
        "none",
        "--client.disableDataExport",
        "true",
        "--browser.gatherUsageStats",
        "false",
        *[arg for key, value in THEME_OPTIONS.items() for arg in (f"--theme.{key}", value)],
    ]


def build_plan(
    environ: Mapping[str, str] | None = None, port: int | None = None, token: str | None = None
) -> LaunchPlan:
    """Prepara una ejecución: puerto, token nuevo (nunca heredado) y entorno del servidor."""
    chosen_port = port if port is not None else free_port()
    chosen_token = token or secrets.token_urlsafe(_TOKEN_BYTES)
    env = {**(os.environ if environ is None else environ), ENV_ACCESS_TOKEN: chosen_token}
    return LaunchPlan(
        command=build_command(chosen_port),
        env=env,
        url=f"http://{HOST}:{chosen_port}/?{URL_TOKEN_PARAM}={chosen_token}",
        port=chosen_port,
    )


def _wait_until_healthy(port: int, server: subprocess.Popen) -> bool:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    url = f"http://{HOST}:{port}/_stcore/health"
    while time.monotonic() < deadline:
        if server.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - URL fija local
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def _stop(server: subprocess.Popen) -> None:
    """Detiene el servidor y sus procesos hijos (el python del venv lanza un proceso aparte)."""
    if server.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603, S607 - orden fija del sistema
            ["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()


def main() -> int:
    plan = build_plan()
    server = subprocess.Popen(plan.command, env=plan.env)  # noqa: S603 - argumentos fijos
    try:
        if not _wait_until_healthy(plan.port, server):
            print("No se pudo iniciar el servidor de la interfaz.", file=sys.stderr)
            return 1
        webbrowser.open(plan.url)
        print(f"_glucosa en ejecución (solo local). Cierra con Ctrl+C. Puerto {plan.port}.")
        return server.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        _stop(server)


if __name__ == "__main__":
    sys.exit(main())
