"""Parser y validación del CSV de LibreView (datos sintéticos)."""

import pytest

from glucosa.errors import LibreFormatError
from glucosa.sources.libre.csv_format import MAX_FILE_BYTES
from glucosa.sources.libre.csv_parser import parse_libre_csv
from glucosa.sources.libre.models import RecordType, TimeFlag
from tests.libre_fixtures import HEADER, PATIENT, SERIAL_A, build_csv, row


def basic_rows():
    return [
        row("hist", "20-10-2026 08:00", 110),
        row("hist", "20-10-2026 08:15", 115),
        row("scan", "20-10-2026 08:20", 118),
        row("food", "20-10-2026 08:30"),
        row("note", "20-10-2026 08:31"),
        row("other", "20-10-2026 08:32"),
    ]


def test_parses_metadata_header_and_classifies_every_row():
    parsed = parse_libre_csv(build_csv(basic_rows()))

    assert parsed.metadata_present is True
    assert parsed.rows_total == 6
    assert [(r.record_type, r.glucose_mg_dl) for r in parsed.readings] == [
        (RecordType.HISTORIC, 110),
        (RecordType.HISTORIC, 115),
        (RecordType.SCAN, 118),
    ]
    assert parsed.other_events == {"alimento": 1, "nota": 1, "otros": 1}
    assert parsed.invalid == ()
    assert (parsed.period_start, parsed.period_end) == ("2026-10-20T08:00", "2026-10-20T08:20")


@pytest.mark.parametrize(
    "kwargs",
    [{"newline": "\n"}, {"bom": True}, {"metadata": False}],
    ids=["lf", "bom", "sin_metadatos"],
)
def test_tolerates_line_endings_bom_and_missing_metadata_row(kwargs):
    parsed = parse_libre_csv(build_csv(basic_rows(), **kwargs))
    assert len(parsed.readings) == 3
    assert parsed.metadata_present is ("metadata" not in kwargs)


def test_wrong_header_names_the_missing_columns_without_guessing():
    header = [c for c in HEADER if c != "Escanear glucosa mg/dL"]
    with pytest.raises(LibreFormatError, match="Escanear glucosa mg/dL"):
        parse_libre_csv(build_csv([], header=header))


def test_file_that_is_not_a_libreview_export_is_rejected_clearly():
    with pytest.raises(LibreFormatError, match="LibreView"):
        parse_libre_csv(b"a,b,c\r\n1,2,3\r\n")


def test_non_utf8_and_oversized_files_are_rejected():
    with pytest.raises(LibreFormatError, match="UTF-8"):
        parse_libre_csv(b"\xff\xfe\x00\x01 no es utf8 \x80\x81")
    with pytest.raises(LibreFormatError, match="tamaño"):
        parse_libre_csv(b"x" * (MAX_FILE_BYTES + 1))


@pytest.mark.parametrize(
    ("cells", "reason"),
    [
        (row("hist", "20-10-2026 08:00", "HI"), "hi"),
        (row("hist", "20-10-2026 08:00", "lo"), "lo"),
        (row("hist", "20-10-2026 08:00", ""), "valor_ausente"),
        (row("hist", "20-10-2026 08:00", "abc"), "valor_no_numerico"),
        (row("hist", "20-10-2026 08:00", "120,5"), "valor_no_entero"),
        (row("hist", "20-10-2026 08:00", "19"), "fuera_de_rango_plausible"),
        (row("hist", "20-10-2026 08:00", "601"), "fuera_de_rango_plausible"),
        (row("hist", "2026-10-20 08:00", "120"), "fecha_invalida"),
        (row("hist", "31-02-2026 08:00", "120"), "fecha_invalida"),
        (row("hist", "20-10-2026 08:00", "120", serial=""), "dispositivo_ausente"),
        (row("scan", "20-10-2026 08:00", "HI"), "hi"),
    ],
)
def test_invalid_rows_are_reported_with_a_reason_and_never_stop_the_import(cells, reason):
    rows = [row("hist", "20-10-2026 07:45", 100), cells, row("hist", "20-10-2026 08:15", 101)]

    parsed = parse_libre_csv(build_csv(rows))

    assert [r.glucose_mg_dl for r in parsed.readings] == [100, 101]
    assert [i.reason for i in parsed.invalid] == [reason]


def test_non_integer_record_type_and_wrong_column_count_are_invalid():
    bad_type = row("hist", "20-10-2026 08:00", 100)
    bad_type[3] = "x"
    short = ["solo", "tres", "celdas"]

    parsed = parse_libre_csv(build_csv([bad_type, short, row("hist", "20-10-2026 08:15", 101)]))

    assert [i.reason for i in parsed.invalid] == ["tipo_invalido", "columnas_inesperadas"]
    assert len(parsed.readings) == 1


def test_invalid_rows_report_the_physical_line_number():
    parsed = parse_libre_csv(
        build_csv([row("hist", "20-10-2026 08:00", 100), row("hist", "20-10-2026 08:15", "HI")])
    )
    # línea 1 metadatos, 2 encabezado, 3 primera fila, 4 segunda fila
    assert parsed.invalid[0].line_number == 4


def test_blank_lines_are_ignored_and_not_counted():
    cells = row("hist", "20-10-2026 08:00", 100)
    parsed = parse_libre_csv(build_csv([cells, [""] * len(HEADER), cells]))
    assert parsed.rows_total == 2


def test_food_notes_patient_and_serial_are_not_retained_in_the_parse_result():
    parsed = parse_libre_csv(build_csv(basic_rows()))
    text = repr(parsed)
    for private in ("ALIMENTO-PRIVADO", "NOTA-PRIVADA", PATIENT, SERIAL_A):
        assert private not in text


def test_dates_are_local_santiago_with_instants_offsets_and_dst_flags():
    parsed = parse_libre_csv(
        build_csv(
            [
                row("hist", "15-08-2026 12:00", 100),  # invierno UTC-4
                row("hist", "15-01-2026 12:00", 101),  # verano UTC-3
                row("hist", "04-04-2026 23:30", 102),  # hora repetida
                row("hist", "06-09-2026 00:30", 103),  # hora inexistente
            ]
        )
    )
    winter, summer, repeated, skipped = parsed.readings

    assert winter.local_minute == "2026-08-15T12:00"
    assert winter.utc_offset_minutes == -240
    assert winter.instant_utc.isoformat() == "2026-08-15T16:00:00+00:00"
    assert summer.utc_offset_minutes == -180
    assert summer.instant_utc.isoformat() == "2026-01-15T15:00:00+00:00"
    assert winter.time_flag is TimeFlag.NORMAL
    assert repeated.time_flag is TimeFlag.AMBIGUOUS
    assert skipped.time_flag is TimeFlag.NONEXISTENT


def test_same_wall_clock_minute_with_different_instants_stays_distinct_in_ordering():
    parsed = parse_libre_csv(
        build_csv([row("hist", "05-04-2026 02:30", 100), row("hist", "05-04-2026 03:10", 101)])
    )
    first, second = parsed.readings
    assert first.instant_utc < second.instant_utc


def test_device_is_kept_as_model_and_serial_for_the_importer_to_pseudonymize():
    parsed = parse_libre_csv(
        build_csv(
            [
                row("hist", "20-10-2026 08:00", 100),
                row("hist", "20-10-2026 08:00", 100, serial="OTRA"),
            ]
        )
    )
    assert {r.serial for r in parsed.readings} == {SERIAL_A, "OTRA"}
