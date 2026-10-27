"""Fuentes simuladas para probar la página Glucosa sin red, claves ni datos reales."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from glucosa.data.timeutil import parse_timestamp
from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.sources.libre.models import (
    ImportSummary,
    RecordType,
    StoredReading,
    StoreStats,
    TimeFlag,
)
from glucosa.ui.glucose_sources import LibreLoad, ManualLoad, SourceStatus, TargetRange

# «Ahora» fijo de las pruebas de interfaz: 26-10-2026 15:00 hora de Santiago.
NOW = datetime(2026, 10, 26, 18, 0, tzinfo=UTC)
START = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # 09:00 locales
FETCHED_AT = datetime(2026, 10, 26, 17, 55, tzinfo=UTC)  # 14:55 locales


def manual_records(with_imported: bool = False, with_unset_moment: bool = False):
    values = [
        (60, GlucoseMoment.WAKING_UP),
        (120, GlucoseMoment.AFTER_LUNCH),
        (260, GlucoseMoment.NOW),
    ]
    records = [
        GlucoseRecord(
            f"m{i}",
            value,
            moment,
            parse_timestamp(f"2026-10-2{3 + i}T09:30:00.000000"),
            "obs <b>x</b>" if i == 1 else None,
            Origin.MANUAL,
        )
        for i, (value, moment) in enumerate(values)
    ]
    if with_imported:
        records.append(
            GlucoseRecord(
                "i0",
                300,
                GlucoseMoment.NOW,
                parse_timestamp("2026-10-25T12:00:00.000000"),
                "Importado desde OtraApp.",
                Origin.IMPORTED,
                "OtraApp",
            )
        )
    if with_unset_moment:
        records.append(
            GlucoseRecord(
                "u0",
                140,
                None,
                parse_timestamp("2026-10-25T13:00:00.000000"),
                None,
                Origin.MANUAL,
            )
        )
    return tuple(sorted(records, key=lambda r: r.measured_at))


def libre_readings(days: int = 4, device: str = "d") -> tuple[StoredReading, ...]:
    readings = []
    for i in range(days * 96):
        instant = START + timedelta(minutes=15 * i)
        readings.append(
            StoredReading(
                device,
                "x",
                instant,
                -240,
                TimeFlag.NORMAL,
                RecordType.HISTORIC,
                90 + (i * 7) % 130,
                1,
            )
        )
    scan_at = START + timedelta(days=3, hours=1, minutes=3)
    readings.append(
        StoredReading(device, "x", scan_at, -240, TimeFlag.NORMAL, RecordType.SCAN, 120, 1)
    )
    return tuple(sorted(readings, key=lambda r: r.instant_utc))


class FakeSources:
    """Fuentes simuladas. ``scenario`` elige el caso; los contadores permiten verificar la caché."""

    def __init__(self, scenario: str = "full") -> None:
        self.scenario = scenario
        self.saved_range: tuple[int, int] | None = None
        self.imported: list[str] = []
        self.manual_calls = 0
        self.libre_calls = 0
        self.marker: str | None = None if scenario == "no_session" else "marcador-1"
        self.libre_error_once = scenario == "libre_flaky"
        self.save_error: Exception | None = None
        self._extra_days = 0  # días de lecturas que agrega una importación simulada

    # ------------------------------------------------------------------ Firebase
    def session_marker(self) -> str | None:
        return self.marker

    def load_manual(self) -> ManualLoad:
        self.manual_calls += 1
        if self.marker is None:
            return ManualLoad(
                SourceStatus.NO_SESSION,
                message="No hay sesión. Ejecuta: python -m glucosa.login login",
            )
        if self.scenario == "firebase_error":
            return ManualLoad(SourceStatus.ERROR, message="Sin conexión con Firebase.")
        records = manual_records(
            with_imported=self.scenario == "with_imported",
            with_unset_moment=self.scenario == "unset_moment",
        )
        return ManualLoad(SourceStatus.OK, records=records, fetched_at=FETCHED_AT)

    # ----------------------------------------------------------------- LibreView
    def _readings(self) -> tuple[StoredReading, ...]:
        readings = libre_readings(4 + self._extra_days)
        if self.scenario == "two_devices":
            readings = tuple(
                sorted((*readings, *libre_readings(4, device="e")), key=lambda r: r.instant_utc)
            )
        if self.scenario == "device_conflict":
            clash = StoredReading(
                "e", "x", START, -240, TimeFlag.NORMAL, RecordType.HISTORIC, 250, 1
            )
            readings = tuple(sorted((*readings, clash), key=lambda r: r.instant_utc))
        return readings

    def load_libre(self) -> LibreLoad:
        self.libre_calls += 1
        if self.scenario == "libre_empty":
            return LibreLoad(SourceStatus.EMPTY)
        if self.scenario == "libre_error":
            return LibreLoad(SourceStatus.ERROR, message="No se pudo abrir la base (clave).")
        if self.libre_error_once:
            self.libre_error_once = False
            return LibreLoad(SourceStatus.ERROR, message="El archivo está en uso. Reintenta.")
        readings = self._readings()
        historic = sum(r.record_type is RecordType.HISTORIC for r in readings)
        stats = StoreStats(
            total=len(readings),
            historic=historic,
            scans=len(readings) - historic,
            period_start="2026-10-20T09:00",
            period_end="2026-10-24T08:45",
            last_import_utc=NOW,
            imports=1,
        )
        return LibreLoad(SourceStatus.OK, readings=readings, stats=stats)

    def libre_signature(self):
        if self.scenario == "libre_empty":
            return None
        return (1 + self._extra_days, 1)

    def import_csv(self, file_name: str, content: bytes) -> ImportSummary:
        self.imported.append(file_name)
        self._extra_days += 1  # la importación agrega un día de lecturas nuevas
        return ImportSummary(
            file_name="exportación [abcd1234]",
            file_sha256="a" * 64,
            file_bytes=len(content),
            same_file_seen_before=False,
            period_start="2026-10-20T09:00",
            period_end="2026-10-24T08:45",
            rows_total=3,
            historic_rows=3,
            scan_rows=0,
            other_events={"alimento": 0, "nota": 0, "otros": 0},
            new=3,
            new_historic=3,
            new_scans=0,
            repeated=0,
            invalid=0,
            invalid_by_reason={},
            conflicts=0,
            rows_in_conflict=0,
            total_consolidated=3,
            total_historic=3,
            total_scans=0,
            imported_at_utc=NOW,
            last_import_utc=NOW,
        )

    # ------------------------------------------------------------ rango objetivo
    def target_range_info(self) -> TargetRange:
        if self.scenario == "no_session":
            return TargetRange(70, 180, notice="Sin sesión de Firebase: se usa 70–180 mg/dL.")
        return TargetRange(70, 180)

    def target_range(self) -> tuple[int, int]:
        info = self.target_range_info()
        return info.low, info.high

    def save_target_range(self, low: int, high: int) -> None:
        if self.save_error is not None:
            raise self.save_error
        self.saved_range = (low, high)
