"""``python -m glucosa.audit``: auditoría de calidad de datos (solo lectura).

Restaura la sesión guardada, lee las cuatro colecciones del propio usuario y
muestra un informe agregado en pantalla. No escribe datos de salud en disco ni
modifica nada en Firestore.
"""

import sys
from datetime import UTC, datetime

from glucosa.audit.loader import fetch_all
from glucosa.audit.report import render_report, run_audit
from glucosa.auth.service import AuthService
from glucosa.auth.token_store import KeyringTokenStore
from glucosa.config import config_from_environment
from glucosa.data.firestore_client import FirestoreReader
from glucosa.errors import GlucosaError
from glucosa.http import default_http


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        config = config_from_environment()
        http = default_http()
        service = AuthService(
            config.require_api_key(), config.require_oauth_client(), http, KeyringTokenStore()
        )
        session = service.restore_session()
        if session is None:
            print("No hay sesión guardada. Ejecuta: python -m glucosa.login login", file=sys.stderr)
            return 1
        raw = fetch_all(FirestoreReader(config.project_id, http), session)
        print(render_report(run_audit(raw, datetime.now(UTC))))
        return 0
    except GlucosaError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
