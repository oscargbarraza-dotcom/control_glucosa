"""Indicador informativo: ¿cuántas mediciones manuales coinciden con un escaneo del sensor?

Es solo descriptivo. **No** deduplica, fusiona ni elimina nada entre Firebase y LibreView.

Solo se evalúan las mediciones manuales que caen dentro del **período cubierto por la
exportación** (por defecto, de la primera a la última lectura de escaneo, ampliado por la
tolerancia; el llamador puede indicar el período de toda la exportación). Las posteriores o
anteriores no pueden tener escaneo en el archivo y se informan aparte (``outside_coverage``):
contarlas en el denominador engañaría.

Una medición manual «coincide» si existe al menos un escaneo (tipo 1) dentro de la tolerancia
temporal (±``time_tolerance_minutes``, inclusive) cuyo valor difiere como máximo
``value_tolerance_mg_dl`` del valor manual. Valores iniciales: ±10 min y 0 mg/dL (valor exacto);
se eligieron con los datos reales: el usuario transcribe lo que ve al escanear el sensor, casi
siempre en los 5 minutos siguientes y con el mismo valor. Un escaneo puede respaldar a varias
mediciones manuales (se cuenta del lado manual).
"""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from glucosa.models.records import GlucoseRecord
from glucosa.sources.libre.models import RecordType, StoredReading


@dataclass(frozen=True)
class MatchParams:
    time_tolerance_minutes: float = 10.0
    value_tolerance_mg_dl: int = 0

    def __post_init__(self) -> None:
        if self.time_tolerance_minutes < 0 or self.value_tolerance_mg_dl < 0:
            raise ValueError("Las tolerancias no pueden ser negativas.")


@dataclass(frozen=True)
class ManualScanMatch:
    manual_total: int  # mediciones manuales evaluadas (dentro del período cubierto)
    matched: int
    outside_coverage: int
    params: MatchParams

    @property
    def label(self) -> str:
        text = f"{self.matched} de {self.manual_total} mediciones manuales coinciden con un escaneo"
        if self.outside_coverage:
            text += f" ({self.outside_coverage} fuera del período cubierto por la exportación)"
        return text


def match_manual_to_scans(
    manual: Sequence[GlucoseRecord],
    scans: Sequence[StoredReading],
    params: MatchParams | None = None,
    coverage: tuple[datetime, datetime] | None = None,
) -> ManualScanMatch:
    params = params or MatchParams()
    candidates = sorted(
        (s.instant_utc, s.glucose_mg_dl) for s in scans if s.record_type is RecordType.SCAN
    )
    instants = [instant for instant, _ in candidates]
    tolerance = timedelta(minutes=params.time_tolerance_minutes)
    if coverage is None and instants:
        coverage = (instants[0] - tolerance, instants[-1] + tolerance)
    matched = evaluated = 0
    for record in manual:
        if coverage is None or not coverage[0] <= record.measured_at <= coverage[1]:
            continue
        evaluated += 1
        low = bisect_left(instants, record.measured_at - tolerance)
        high = bisect_right(instants, record.measured_at + tolerance)
        if any(
            abs(value - record.value_mg_dl) <= params.value_tolerance_mg_dl
            for _, value in candidates[low:high]
        ):
            matched += 1
    return ManualScanMatch(evaluated, matched, len(manual) - evaluated, params)
