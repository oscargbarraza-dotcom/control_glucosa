"""Vista unificada para mostrar glucosa de las dos fuentes sin perder su origen.

Solo sirve para presentar (tabla, gráfico, filtros). Las estadísticas se calculan **por fuente**
y nunca sobre la mezcla, y no se deduplica ni fusiona nada entre Firebase y LibreView.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from glucosa.models.records import GlucoseMoment, GlucoseRecord, Origin
from glucosa.sources.libre.models import RecordType, StoredReading


class Source(StrEnum):
    FIREBASE = "firebase"
    LIBREVIEW = "libreview"


class Kind(StrEnum):
    MANUAL = "manual"  # medición registrada a mano en la app Android (Firebase)
    IMPORTED = "imported"  # medición de Firebase marcada «Importado/Tomado desde X»
    SENSOR = "sensor"  # historial del sensor (LibreView, tipo 0)
    SCAN = "scan"  # escaneo del sensor (LibreView, tipo 1)


class Band(StrEnum):
    BELOW = "below"
    IN_RANGE = "in_range"
    ABOVE = "above"


SOURCE_LABELS = {Source.FIREBASE: "Firebase", Source.LIBREVIEW: "LibreView"}
KIND_LABELS = {
    Kind.MANUAL: "Medición manual",
    Kind.IMPORTED: "Medición importada",
    Kind.SENSOR: "Historial del sensor",
    Kind.SCAN: "Escaneo del sensor",
}
BAND_LABELS = {
    Band.BELOW: "Bajo el rango",
    Band.IN_RANGE: "Dentro del rango",
    Band.ABOVE: "Sobre el rango",
}


@dataclass(frozen=True)
class GlucosePoint:
    instant: datetime  # con zona horaria
    value: int  # mg/dL
    source: Source
    kind: Kind
    moment: GlucoseMoment | None = None  # solo registros de Firebase (declarado por el usuario)
    comment: str | None = None  # solo registros de Firebase


def classify(value: int, low: int, high: int) -> Band:
    """Bajo: v < mín · En rango: mín ≤ v ≤ máx · Sobre: v > máx (límites inclusivos en el rango)."""
    if value < low:
        return Band.BELOW
    return Band.IN_RANGE if value <= high else Band.ABOVE


def manual_points(records: Iterable[GlucoseRecord]) -> list[GlucosePoint]:
    """Registros de Firebase conservados todos; la procedencia decide si son manuales o importados.

    «Importado desde X» no se asume lectura del sensor: solo se rotula como importada.
    """
    return [
        GlucosePoint(
            instant=r.measured_at,
            value=r.value_mg_dl,
            source=Source.FIREBASE,
            kind=Kind.IMPORTED if r.origin is Origin.IMPORTED else Kind.MANUAL,
            moment=r.moment,
            comment=r.comment,
        )
        for r in records
    ]


def sensor_points(readings: Iterable[StoredReading]) -> list[GlucosePoint]:
    return [
        GlucosePoint(
            instant=r.instant_utc,
            value=r.glucose_mg_dl,
            source=Source.LIBREVIEW,
            kind=Kind.SENSOR if r.record_type is RecordType.HISTORIC else Kind.SCAN,
        )
        for r in readings
    ]
