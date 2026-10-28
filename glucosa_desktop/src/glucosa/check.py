"""``python -m glucosa.check``: diagnóstico de la instalación, sin mostrar secretos.

Permite confirmar que la configuración está completa y segura sin pegar nada
en un chat ni abrir archivos con credenciales.
"""

import sys
from dataclasses import dataclass
from typing import Any

from glucosa.config import AppConfig, config_from_environment
from glucosa.errors import ConfigError
from glucosa.paths import default_data_dir, is_inside_onedrive

_SECURE_KEYRING = "WinVaultKeyring"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_api_key(config: AppConfig) -> CheckResult:
    name = "API key de Firebase"
    if config.api_key:
        return CheckResult(name, True, "definida")
    return CheckResult(name, False, "falta GLUCOSA_FIREBASE_API_KEY")


def _check_oauth_client(config: AppConfig) -> CheckResult:
    name = "Cliente OAuth de escritorio"
    try:
        client = config.require_oauth_client()
    except ConfigError as exc:
        return CheckResult(name, False, str(exc))
    short_id = client.client_id.split("-")[0][:6] + "…"
    return CheckResult(
        name, True, f"válido (tipo escritorio, id {short_id}, proyecto {client.project_id})"
    )


def _check_data_dir() -> CheckResult:
    name = "Carpeta de datos local"
    path = default_data_dir()
    if is_inside_onedrive(path):
        return CheckResult(name, False, f"{path} está dentro de OneDrive")
    return CheckResult(name, True, f"{path} (fuera de OneDrive)")


def _check_keyring(backend: Any) -> CheckResult:
    name = "Almacén de credenciales"
    backend_name = type(backend).__name__
    if backend_name == _SECURE_KEYRING:
        return CheckResult(name, True, "Administrador de credenciales de Windows")
    return CheckResult(name, False, f"backend no seguro o desconocido: {backend_name}")


def run_checks(config: AppConfig, keyring_backend: Any | None = None) -> list[CheckResult]:
    if keyring_backend is None:
        import keyring

        keyring_backend = keyring.get_keyring()
    return [
        _check_api_key(config),
        _check_oauth_client(config),
        _check_data_dir(),
        _check_keyring(keyring_backend),
    ]


def main() -> int:
    results = run_checks(config_from_environment())
    for result in results:
        print(f"[{'OK' if result.ok else 'FALLA'}] {result.name}: {result.detail}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
