"""``python -m glucosa.libre_import <archivo.csv> [--db RUTA]``: importa un CSV de LibreView.

Lee el CSV (nunca lo modifica, mueve ni borra), lo consolida en la base local cifrada y muestra
un resumen con conteos. No imprime valores de glucosa ni datos personales.
"""

import argparse
import sys
from pathlib import Path

from glucosa.errors import GlucosaError
from glucosa.paths import libre_db_path
from glucosa.sources.libre.importer import import_libre_csv
from glucosa.sources.libre.store import LibreStore
from glucosa.sources.libre.summary import render_summary
from glucosa.storage.secure_store import KeyProvider, KeyringKeyProvider


def main(argv: list[str] | None = None, key_provider: KeyProvider | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m glucosa.libre_import")
    parser.add_argument("csv", type=Path, help="CSV exportado desde LibreView")
    parser.add_argument("--db", type=Path, default=None, help="base cifrada (por defecto, local)")
    args = parser.parse_args(argv)
    try:
        if not args.csv.is_file():
            print("[ERROR] No se encontró el archivo indicado.", file=sys.stderr)
            return 1
        content = args.csv.read_bytes()  # solo lectura
        db_path = args.db or libre_db_path()
        with LibreStore.open(db_path, key_provider or KeyringKeyProvider()) as store:
            summary = import_libre_csv(content, args.csv.name, store)
        print(render_summary(summary))
        return 0
    except GlucosaError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(
            f"[ERROR] No se pudo leer o escribir un archivo ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - nunca mostrar traceback ni detalles internos
        print(f"[ERROR] Falla inesperada ({type(exc).__name__}).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
