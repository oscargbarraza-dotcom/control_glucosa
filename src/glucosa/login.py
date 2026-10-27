"""``python -m glucosa.login [login|status|logout]``: sesión y comprobación de lectura.

* ``login``: inicia sesión con Google (abre el navegador) y comprueba la lectura de Firestore.
* ``status``: restaura la sesión guardada y comprueba la lectura de Firestore.
* ``logout``: borra la sesión guardada en el Administrador de credenciales.
* ``compare-uid [UID]``: compara, sin red, el UID guardado de la sesión con el UID de Firebase
  Console. Nunca imprime ninguno de los dos completos.

La comprobación de lectura solo cuenta documentos por colección (consultas de
agregación): no descarga ni muestra datos de salud. Los identificadores se
imprimen enmascarados.
"""

import argparse
import secrets
import sys
import webbrowser

from glucosa.auth.service import AuthService
from glucosa.auth.session import AuthSession
from glucosa.auth.token_store import KeyringTokenStore
from glucosa.config import AppConfig, config_from_environment
from glucosa.data.firestore_client import FirestoreReader
from glucosa.errors import GlucosaError
from glucosa.http import default_http
from glucosa.identifiers import is_valid_uid

COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("Glucosa", "glucose_measurements"),
    ("Comidas", "meals"),
    ("Medicamentos", "medication_intakes"),
    ("Biometría", "biometric_measurements"),
)


def mask_email(email: str | None) -> str:
    if not email:
        return "(sin correo)"
    local, separator, domain = email.partition("@")
    if not separator or not local:
        return "(correo no válido)"
    return f"{local[0]}***@{domain}"


def mask_uid(uid: str) -> str:
    return f"{uid[:4]}…{uid[-4:]}"


def read_counts(reader: FirestoreReader, session: AuthSession) -> list[tuple[str, int]]:
    """Cuenta los documentos de las cuatro colecciones del propio usuario (solo lectura)."""
    return [
        (label, reader.count_collection(session.uid, collection, session.id_token))
        for label, collection in COLLECTIONS
    ]


def _ask_uid() -> str | None:
    """Pide el UID por teclado; None si no hay terminal interactivo."""
    if not sys.stdin.isatty():
        return None
    try:
        return input("UID completo de Firebase Console: ")
    except EOFError:
        return None


def _compare_uid(provided: str | None, store: KeyringTokenStore) -> int:
    """Compara el UID guardado con el de Firebase Console (local, sin red)."""
    stored = store.load()
    if stored is None:
        print("No hay sesión guardada. Ejecuta: python -m glucosa.login login", file=sys.stderr)
        return 1
    if provided is None:
        provided = _ask_uid()
        if provided is None:
            print(
                "Indica el UID: python -m glucosa.login compare-uid <UID de Firebase Console>",
                file=sys.stderr,
            )
            return 1
    provided = provided.strip()
    if not is_valid_uid(provided):
        print("El UID indicado no tiene el formato esperado (letras y números).", file=sys.stderr)
        return 1
    matches = secrets.compare_digest(provided.encode("utf-8"), stored.uid.encode("utf-8"))
    if matches:
        print(
            f"COINCIDE: la sesión y Firebase Console tienen el mismo UID ({mask_uid(stored.uid)})."
        )
        return 0
    print(
        "NO COINCIDE: "
        f"sesión {mask_uid(stored.uid)} (largo {len(stored.uid)}) ≠ "
        f"indicado {mask_uid(provided)} (largo {len(provided)})."
    )
    return 1


def _open_browser(url: str) -> bool:
    if not webbrowser.open(url):
        print(f"No se pudo abrir el navegador. Abre manualmente esta dirección:\n{url}")
    return True  # se sigue esperando el callback


def _build_service(config: AppConfig) -> AuthService:
    return AuthService(
        api_key=config.require_api_key(),
        client=config.require_oauth_client(),
        http=default_http(),
        token_store=KeyringTokenStore(),
        open_browser=_open_browser,
    )


def _report_read_access(config: AppConfig, session: AuthSession) -> None:
    print(f"Usuario: {mask_uid(session.uid)}  Correo: {mask_email(session.email)}")
    reader = FirestoreReader(config.project_id, default_http())
    for label, count in read_counts(reader, session):
        print(f"  {label}: {count} documentos en Firestore")
    print("Lectura de Firestore verificada (solo conteos, modo lectura).")


def _run(command: str, config: AppConfig) -> int:
    service = _build_service(config)
    if command == "logout":
        service.sign_out()
        print("Sesión cerrada: se borró el token guardado.")
        return 0
    if command == "login":
        result = service.sign_in()
        print("Inicio de sesión con Google y Firebase: OK.")
        if result.uid_changed:
            print("AVISO: el usuario difiere del guardado anteriormente.")
        session = result.session
    else:
        restored = service.restore_session()
        if restored is None:
            print("No hay sesión guardada. Ejecuta: python -m glucosa.login login")
            return 1
        print("Sesión restaurada desde el Administrador de credenciales: OK.")
        session = restored
    _report_read_access(config, session)
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m glucosa.login")
    parser.add_argument(
        "command",
        nargs="?",
        default="login",
        choices=["login", "status", "logout", "compare-uid"],
    )
    parser.add_argument("uid", nargs="?", help="UID de Firebase Console (solo compare-uid)")
    args = parser.parse_args(argv)
    try:
        if args.command == "compare-uid":
            return _compare_uid(args.uid, KeyringTokenStore())
        return _run(args.command, config_from_environment())
    except GlucosaError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - nunca mostrar traceback ni el detalle interno
        print(f"[ERROR] Falla inesperada ({type(exc).__name__}).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
