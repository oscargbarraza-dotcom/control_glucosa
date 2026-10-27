"""La configuración de Streamlit es parte de la seguridad: la app maneja datos de salud."""

import tomllib
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"


def load() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_server_only_listens_on_loopback():
    assert load()["server"]["address"] == "127.0.0.1"


def test_cross_origin_protections_are_enabled():
    server = load()["server"]
    assert server["enableCORS"] is True  # false permitiría WebSocket desde cualquier origen
    assert server["enableXsrfProtection"] is True
    assert set(server["allowedHosts"]) == {"127.0.0.1", "localhost"}


def test_upload_size_is_capped_close_to_the_importer_limit():
    assert load()["server"]["maxUploadSize"] == 30


def test_error_details_and_data_export_are_disabled_in_the_config_file_too():
    client = load()["client"]
    assert client["showErrorDetails"] == "none"
    assert client["disableDataExport"] is True


def test_usage_statistics_are_disabled():
    assert load()["browser"]["gatherUsageStats"] is False


def test_theme_is_dark_with_neutral_controls_and_matches_the_launcher():
    from glucosa.__main__ import THEME_OPTIONS

    theme = load()["theme"]
    assert theme == THEME_OPTIONS
    assert theme["base"] == "dark"
    # El rojo queda para «bajo el rango»: los controles no pueden usarlo.
    red, green, blue = (int(theme["primaryColor"][i : i + 2], 16) for i in (1, 3, 5))
    assert not (red > green + 60 and red > blue + 60)
