from pathlib import Path

from platformdirs import user_data_dir

from glucosa.paths import default_data_dir


def test_default_is_the_per_user_local_app_data_folder():
    assert default_data_dir() == Path(user_data_dir("glucosa", appauthor=False))


def test_override_takes_precedence(tmp_path):
    assert default_data_dir(str(tmp_path)) == tmp_path


def test_blank_override_is_ignored():
    assert default_data_dir("  ") == default_data_dir()
