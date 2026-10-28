"""Asociación temporal comida ↔ glucosa (capa analítica, solo descriptiva).

Aprobado en la Etapa D3:

* Ventanas por comida, mutuamente excluyentes: previa ``[−60, −5)``, al comer ``[−5, +5]`` y
  posterior ``(+5, +180]`` minutos, sobre instantes UTC y con búsqueda binaria.
* **Glucosa de referencia** (lectura más cercana a la comida dentro de ``[−60, +5]``, anterior en
  empates) distinta de la **glucosa previa** (última lectura estrictamente anterior a «Al comer»).
  Una referencia posterior al registro se marca ``after_record`` y no se presenta como previa.
* Resultados **separados por fuente**; la selección combinada solo desempata o elige una lectura
  representativa (manual › importada › sensor). Sin promedios entre fuentes.
* Sin área bajo la curva, sin interpolar y sin causalidad. Los estadísticos del sensor exigen
  cobertura ≥ 70 % (la misma regla del TIR) y se informa la cobertura real.
* Las coincidencias manual ↔ LibreView se marcan como «probables»; nada se borra ni se recorta.
* Sin consultar el reloj: la hora actual se inyecta (``now``).
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum

from glucosa.analytics.glucose_sensor import SensorSample, TirParams, compute_tir
from glucosa.analytics.meal_milestones import (
    MILESTONES,
    MilestoneParams,
    MilestoneResult,
    compute_milestones,
    mark_shared,
    representative,
)
from glucosa.analytics.meal_readings import (
    SERIES_SOURCES,
    SOURCE_PRIORITY,
    GlucoseInputs,
    ProbableCoincidence,
    Reading,
    ReadingIndex,
    ReadingSource,
    WindowReading,
    find_coincidences,
)
from glucosa.analytics.meal_view import MealView

MIN_COVERAGE = 0.70
_COVERAGE_TOLERANCE = 1e-6
_MICRO = timedelta(microseconds=1)
NEAR_SIMULTANEOUS_MINUTES = 15
OVERLAP_MINUTES = 240  # ventanas [−60, +180] de dos comidas se tocan si distan ≤ 240 min


class Window(StrEnum):
    PRE = "pre"  # [−60, −5)
    AT = "at"  # [−5, +5]
    POST = "post"  # (+5, +180]


WINDOW_ORDER = (Window.PRE, Window.AT, Window.POST)


@dataclass(frozen=True)
class WindowParams:
    pre_minutes: int = 60
    at_before_minutes: int = 5
    at_after_minutes: int = 5
    post_minutes: int = 180

    def __post_init__(self) -> None:
        values = (
            self.pre_minutes,
            self.at_before_minutes,
            self.at_after_minutes,
            self.post_minutes,
        )
        if any(v <= 0 for v in values) or self.pre_minutes <= self.at_before_minutes:
            raise ValueError("Las ventanas deben tener duraciones positivas y coherentes.")


@dataclass(frozen=True)
class AssociationParams:
    windows: WindowParams = field(default_factory=WindowParams)
    milestones: MilestoneParams = field(default_factory=MilestoneParams)
    min_coverage: float = MIN_COVERAGE


class Availability(StrEnum):
    """Disponibilidad de una ventana. Distingue export desactualizado, huecos reales y ausencias."""

    SUFFICIENT = "sufficient"  # dentro del export y cobertura ≥ umbral (no es «completo»)
    GAPS = "gaps"  # dentro del export, pero cobertura < umbral: huecos reales
    EXPORT_OUTDATED = (
        "export_outdated"  # la ventana empieza después de la última lectura del export
    )
    BEFORE_EXPORT = "before_export"  # la ventana termina antes de la primera lectura del export
    PARTIAL_EXPORT = "partial_export"  # la ventana cruza el inicio o el fin del export
    NO_SENSOR_DATA = "no_sensor_data"  # no hay datos de LibreView
    PRESENT = "present"  # manual/importada: hay mediciones
    ABSENT = "absent"  # manual/importada: sin mediciones


@dataclass(frozen=True)
class WindowSummary:
    window: Window
    source: ReadingSource
    readings: tuple[WindowReading, ...]
    availability: Availability
    coverage: float | None  # sensor: sobre la ventana completa
    coverage_within_export: float | None  # sensor: sobre la parte que el export abarca
    stats_allowed: bool
    complete: bool  # la ventana ya terminó según la hora actual inyectada
    minimum: WindowReading | None = None
    maximum: WindowReading | None = None  # el primero si hay valores iguales

    @property
    def n(self) -> int:
        return len(self.readings)


@dataclass(frozen=True)
class ReferenceReading:
    reading: WindowReading
    after_record: bool  # la lectura es posterior al registro (nunca se presenta como «previa»)
    window: Window  # PRE o AT


@dataclass(frozen=True)
class Neighbor:
    uuid: str
    minutes: float  # otra comida − esta comida
    type_label: str


@dataclass(frozen=True)
class MealGlucose:
    uuid: str
    eaten_at: datetime
    summaries: dict[tuple[Window, ReadingSource], WindowSummary]
    scans: dict[Window, tuple[WindowReading, ...]]
    reference: dict[ReadingSource, ReferenceReading]
    combined_reference: ReferenceReading | None
    previous: dict[ReadingSource, WindowReading]
    combined_previous: WindowReading | None
    rise: dict[ReadingSource, int]  # máximo observado − referencia, misma fuente
    any_readings: dict[Window, bool]
    milestones: dict[int, dict[ReadingSource, MilestoneResult]]
    milestone_representative: dict[int, MilestoneResult | None]
    neighbors: tuple[Neighbor, ...] = ()
    overlapping: tuple[Neighbor, ...] = ()
    isolated: bool = True
    near_simultaneous: bool = False
    crossed_milestones: dict[int, tuple[str, ...]] = field(default_factory=dict)
    shared_reading_ids: frozenset[str] = frozenset()

    def summary(self, window: Window, source: ReadingSource) -> WindowSummary:
        return self.summaries[(window, source)]

    @property
    def overlaps_windows(self) -> bool:
        return bool(self.overlapping)


@dataclass(frozen=True)
class MealAssociation:
    meals: tuple[MealGlucose, ...]
    coincidences: tuple[ProbableCoincidence, ...]
    equivalents: dict[str, str]  # id de lectura de LibreView → id de la manual con la que coincide
    export_span: tuple[datetime, datetime] | None
    params: AssociationParams

    def equivalent_manual_of(self, reading_id: str) -> str | None:
        return self.equivalents.get(reading_id)


# ------------------------------------------------------------------------ ventanas
def _bounds(meal_time: datetime, window: Window, p: WindowParams):
    """(inicio, fin, inicio_incluido, fin_incluido) de la ventana."""
    if window is Window.PRE:
        return (
            meal_time - timedelta(minutes=p.pre_minutes),
            meal_time - timedelta(minutes=p.at_before_minutes),
            True,
            False,
        )
    if window is Window.AT:
        return (
            meal_time - timedelta(minutes=p.at_before_minutes),
            meal_time + timedelta(minutes=p.at_after_minutes),
            True,
            True,
        )
    return (
        meal_time + timedelta(minutes=p.at_after_minutes),
        meal_time + timedelta(minutes=p.post_minutes),
        False,
        True,
    )


def _in_window(index: ReadingIndex, meal_time: datetime, window: Window, p: WindowParams):
    start, end, include_start, include_end = _bounds(meal_time, window, p)
    found = index.between(start, end, include_start=include_start, include_end=include_end)
    return tuple(WindowReading(r, (r.instant - meal_time).total_seconds() / 60) for r in found)


def _extremes(readings: tuple[WindowReading, ...]):
    if not readings:
        return None, None
    lowest = min(readings, key=lambda w: (w.reading.value, w.reading.instant, w.reading.id))
    highest = min(readings, key=lambda w: (-w.reading.value, w.reading.instant, w.reading.id))
    return lowest, highest


# ----------------------------------------------------------------------- sensor
def _coverage(inputs, index, start, end, params):
    """Cobertura (0–1) del intervalo con la regla del TIR (tramos ≤ 30 min, sin interpolar)."""
    if end <= start:
        return 0.0
    margin = timedelta(minutes=31)
    nearby = index.between(start - margin, end + margin)
    samples = [SensorSample(r.instant, r.value) for r in nearby]
    tir = TirParams(min_readings=0, min_coverage=0.0)
    return compute_tir(samples, start, end, tir).coverage


def _sensor_summary(window, meal_time, readings, inputs, index, now, params) -> WindowSummary:
    start, end, _, include_end = _bounds(meal_time, window, params.windows)
    stop = end + _MICRO if include_end else end
    complete = end <= now
    if not inputs.sensor or inputs.export_span is None:
        return WindowSummary(
            window,
            ReadingSource.SENSOR,
            readings,
            Availability.NO_SENSOR_DATA,
            None,
            None,
            False,
            complete,
        )
    export_start, export_end = inputs.export_span
    coverage = _coverage(inputs, index, start, stop, params)
    inside_start, inside_end = max(start, export_start), min(stop, export_end)
    within = (
        coverage
        if (inside_start, inside_end) == (start, stop)
        else _coverage(inputs, index, inside_start, inside_end, params)
    )
    if start > export_end:
        status = Availability.EXPORT_OUTDATED
    elif end < export_start:
        status = Availability.BEFORE_EXPORT
    elif start < export_start or end > export_end:
        status = Availability.PARTIAL_EXPORT
    elif coverage + _COVERAGE_TOLERANCE >= params.min_coverage:
        status = Availability.SUFFICIENT
    else:
        status = Availability.GAPS
    allowed = bool(readings) and coverage + _COVERAGE_TOLERANCE >= params.min_coverage
    lowest, highest = _extremes(readings) if allowed else (None, None)
    return WindowSummary(
        window,
        ReadingSource.SENSOR,
        readings,
        status,
        coverage,
        within,
        allowed,
        complete,
        lowest,
        highest,
    )


def _point_summary(window, source, meal_time, readings, now, params) -> WindowSummary:
    end = _bounds(meal_time, window, params.windows)[1]
    present = bool(readings)
    lowest, highest = _extremes(readings)
    return WindowSummary(
        window,
        source,
        readings,
        Availability.PRESENT if present else Availability.ABSENT,
        None,
        None,
        present,
        end <= now,
        lowest,
        highest,
    )


# ----------------------------------------------------- referencia, previa y estadísticos
def _reference_candidates(index, meal_time, p: WindowParams) -> tuple[Reading, ...]:
    return index.between(
        meal_time - timedelta(minutes=p.pre_minutes),
        meal_time + timedelta(minutes=p.at_after_minutes),
    )


def _as_reference(found: Reading, meal_time: datetime, p: WindowParams) -> ReferenceReading:
    delta = (found.instant - meal_time).total_seconds() / 60
    window = Window.PRE if delta < -p.at_before_minutes else Window.AT
    return ReferenceReading(WindowReading(found, delta), delta > 0, window)


def _closest(candidates: Sequence[Reading], meal_time: datetime) -> Reading | None:
    return min(
        candidates,
        key=lambda r: (
            abs(r.instant - meal_time),
            r.instant,
            SOURCE_PRIORITY[r.source],
            r.id,
        ),
        default=None,
    )


def _previous_of(index, meal_time, p: WindowParams) -> Reading | None:
    start, end, include_start, include_end = _bounds(meal_time, Window.PRE, p)
    found = index.between(start, end, include_start=include_start, include_end=include_end)
    return max(found, key=lambda r: (r.instant, r.id), default=None)


def _rise(summaries, reference, source) -> int | None:
    post = summaries[(Window.POST, source)]
    if source not in reference or not post.stats_allowed or post.maximum is None:
        return None
    return post.maximum.reading.value - reference[source].reading.reading.value


def _neighbor(other: MealView, meal: MealView) -> Neighbor:
    return Neighbor(
        other.uuid, (other.eaten_at - meal.eaten_at).total_seconds() / 60, other.type_label
    )


# --------------------------------------------------------------------- orquestación
def associate_meals(
    meals: Sequence[MealView],
    inputs: GlucoseInputs,
    now: datetime,
    params: AssociationParams | None = None,
) -> MealAssociation:
    """Asocia cada comida con la glucosa de sus ventanas, referencia, previa y hitos.

    ``now`` (con zona horaria) se inyecta: determina qué hitos están pendientes y qué ventanas
    siguen abiertas; la capa nunca lee el reloj del sistema.
    """
    params = params or AssociationParams()
    ordered = sorted(meals, key=lambda m: (m.eaten_at, m.uuid))
    indexes = {source: ReadingIndex(inputs.series(source)) for source in SERIES_SOURCES}
    scan_index = ReadingIndex(inputs.scans)
    coincidences = find_coincidences(inputs.manual, inputs.scans, inputs.sensor)
    equivalents = {
        c.other_id: c.manual_id for c in coincidences if c.kind.value == "manual_history"
    }
    equivalents.update(
        {c.other_id: c.manual_id for c in coincidences if c.kind.value == "manual_scan"}
    )
    built = [
        _build(meal, inputs, indexes, scan_index, equivalents, now, params) for meal in ordered
    ]
    built = _with_neighbors(built, ordered, params)
    shared = mark_shared({m.uuid: m.milestones for m in built})
    final = tuple(replace(m, milestones=shared[m.uuid]) for m in built)
    final = tuple(
        replace(m, milestone_representative={k: representative(v) for k, v in m.milestones.items()})
        for m in final
    )
    return MealAssociation(final, coincidences, equivalents, inputs.export_span, params)


def _all_summaries(t, inputs, indexes, now, params):
    summaries: dict[tuple[Window, ReadingSource], WindowSummary] = {}
    for window in WINDOW_ORDER:
        for source in SERIES_SOURCES:
            found = _in_window(indexes[source], t, window, params.windows)
            summaries[(window, source)] = (
                _sensor_summary(window, t, found, inputs, indexes[source], now, params)
                if source is ReadingSource.SENSOR
                else _point_summary(window, source, t, found, now, params)
            )
    return summaries


def _references(t, indexes, equivalents, params):
    """Referencia y previa por fuente, más las representativas de la selección combinada."""
    reference, previous = {}, {}
    candidates: list[Reading] = []
    previous_candidates: list[Reading] = []
    for source in SERIES_SOURCES:
        pool = _reference_candidates(indexes[source], t, params.windows)
        found = _closest(pool, t)
        if found is not None:
            reference[source] = _as_reference(found, t, params.windows)
        candidates.extend(pool)
        before = _previous_of(indexes[source], t, params.windows)
        if before is not None:
            previous[source] = WindowReading(before, (before.instant - t).total_seconds() / 60)
            previous_candidates.append(before)
    chosen = _closest(_without_equivalents(candidates, equivalents), t)
    latest = min(
        previous_candidates,
        key=lambda r: (-r.instant.timestamp(), SOURCE_PRIORITY[r.source], r.id),
        default=None,
    )
    combined_reference = _as_reference(chosen, t, params.windows) if chosen else None
    combined_previous = (
        WindowReading(latest, (latest.instant - t).total_seconds() / 60) if latest else None
    )
    return reference, previous, combined_reference, combined_previous


def _build(meal, inputs, indexes, scan_index, equivalents, now, params) -> MealGlucose:
    t = meal.eaten_at
    summaries = _all_summaries(t, inputs, indexes, now, params)
    reference, previous, combined_reference, combined_previous = _references(
        t, indexes, equivalents, params
    )
    rise = {s: v for s in SERIES_SOURCES if (v := _rise(summaries, reference, s)) is not None}
    return MealGlucose(
        uuid=meal.uuid,
        eaten_at=t,
        summaries=summaries,
        scans={w: _in_window(scan_index, t, w, params.windows) for w in WINDOW_ORDER},
        reference=reference,
        combined_reference=combined_reference,
        previous=previous,
        combined_previous=combined_previous,
        rise=rise,
        any_readings={
            w: any(summaries[(w, s)].readings for s in SERIES_SOURCES) for w in WINDOW_ORDER
        },
        milestones=compute_milestones(meal.uuid, t, inputs, indexes, now, params.milestones),
        milestone_representative={},
    )


def _without_equivalents(candidates: list[Reading], equivalents: dict[str, str]) -> list[Reading]:
    """Para la selección combinada, una lectura de LibreView equivalente a una manual candidata no
    compite (la manual la representa). Los registros originales no se tocan."""
    manual_ids = {r.id for r in candidates if r.source is ReadingSource.MANUAL}
    return [
        r
        for r in candidates
        if not (r.source is not ReadingSource.MANUAL and equivalents.get(r.id) in manual_ids)
    ]


# ------------------------------------------------------ vecinas, cruces y lecturas compartidas
def _by_distance(others, meal) -> tuple[Neighbor, ...]:
    return tuple(sorted((_neighbor(o, meal) for o in others), key=lambda n: (n.minutes, n.uuid)))


def _relations(meal: MealView, others, params: AssociationParams) -> dict:
    """Comidas vecinas (rango [−60, +180]), ventanas que se tocan y hitos cruzados."""
    pre = timedelta(minutes=params.windows.pre_minutes)
    post = timedelta(minutes=params.windows.post_minutes)
    in_range = [o for o in others if meal.eaten_at - pre <= o.eaten_at <= meal.eaten_at + post]
    overlapping = _by_distance(others, meal)
    return {
        "neighbors": _by_distance(in_range, meal),
        "overlapping": overlapping,
        "isolated": not in_range,
        "near_simultaneous": any(abs(n.minutes) <= NEAR_SIMULTANEOUS_MINUTES for n in overlapping),
        "crossed_milestones": {
            minutes: tuple(
                o.uuid
                for o in others
                if meal.eaten_at < o.eaten_at <= meal.eaten_at + timedelta(minutes=minutes)
            )
            for minutes in MILESTONES
        },
    }


def _with_neighbors(built, ordered, params: AssociationParams):
    times = [m.eaten_at for m in ordered]
    reach = timedelta(minutes=OVERLAP_MINUTES)
    usage = Counter(reading_id for m in built for reading_id in _reading_ids(m))
    result = []
    for position, (outcome, meal) in enumerate(zip(built, ordered, strict=True)):
        low = bisect_left(times, meal.eaten_at - reach)
        high = bisect_right(times, meal.eaten_at + reach)
        others = [ordered[i] for i in range(low, high) if i != position]
        result.append(
            replace(
                outcome,
                shared_reading_ids=frozenset(i for i in _reading_ids(outcome) if usage[i] > 1),
                **_relations(meal, others, params),
            )
        )
    return result


def _reading_ids(outcome: MealGlucose) -> set[str]:
    return {w.reading.id for s in outcome.summaries.values() for w in s.readings}


# ------------------------------------------------------------------ indicadores y avisos
def unique_reading_count(outcome: MealGlucose, window: Window, association: MealAssociation) -> int:
    """Lecturas únicas de la ventana (manual + importada + sensor): una lectura del sensor que
    coincide con una manual de la misma ventana no se cuenta dos veces. No incluye escaneos."""
    manual_ids = {w.reading.id for w in outcome.summary(window, ReadingSource.MANUAL).readings}
    total = 0
    for source in SERIES_SOURCES:
        for item in outcome.summary(window, source).readings:
            if (
                source is ReadingSource.SENSOR
                and association.equivalent_manual_of(item.reading.id) in manual_ids
            ):
                continue
            total += 1
    return total


@dataclass(frozen=True)
class ExportNotice:
    has_export: bool
    export_end: datetime | None
    meals_after_export: int
    meals_crossing_export_end: int
    first_meal_after: datetime | None

    @property
    def needs_attention(self) -> bool:
        return (
            not self.has_export or self.meals_after_export > 0 or self.meals_crossing_export_end > 0
        )


def export_notice(association: MealAssociation) -> ExportNotice:
    """Aviso informativo: comidas posteriores (o que cruzan el final) al export de LibreView."""
    if association.export_span is None:
        return ExportNotice(False, None, 0, 0, None)
    end = association.export_span[1]
    post = timedelta(minutes=association.params.windows.post_minutes)
    after = [m for m in association.meals if m.eaten_at > end]
    crossing = [m for m in association.meals if m.eaten_at <= end < m.eaten_at + post]
    return ExportNotice(True, end, len(after), len(crossing), after[0].eaten_at if after else None)


@dataclass(frozen=True)
class SourceCoverage:
    meals: int
    with_pre: int
    with_post: int
    with_both: int
    sufficient_pre: int  # ventanas con estadísticos permitidos (sensor: cobertura ≥ umbral)
    sufficient_post: int
    with_reference: int


def coverage_counts(association: MealAssociation) -> dict[ReadingSource, SourceCoverage]:
    counts = {}
    for source in SERIES_SOURCES:
        pre = [m.summary(Window.PRE, source) for m in association.meals]
        post = [m.summary(Window.POST, source) for m in association.meals]
        counts[source] = SourceCoverage(
            meals=len(association.meals),
            with_pre=sum(s.n > 0 for s in pre),
            with_post=sum(s.n > 0 for s in post),
            with_both=sum(a.n > 0 and b.n > 0 for a, b in zip(pre, post, strict=True)),
            sufficient_pre=sum(s.stats_allowed for s in pre),
            sufficient_post=sum(s.stats_allowed for s in post),
            with_reference=sum(source in m.reference for m in association.meals),
        )
    return counts


def availability_label(summary: WindowSummary) -> str:
    """Texto para la interfaz; la cobertura real siempre se muestra."""
    percent = "—" if summary.coverage is None else f"{summary.coverage * 100:.0f} %"
    return {
        Availability.SUFFICIENT: f"Cobertura suficiente ({percent})",
        Availability.GAPS: f"Con huecos del sensor (cobertura {percent})",
        Availability.PARTIAL_EXPORT: f"Parcialmente fuera del export (cobertura {percent})",
        Availability.EXPORT_OUTDATED: (
            "Export desactualizado: la ventana es posterior a su última lectura"
        ),
        Availability.BEFORE_EXPORT: "Anterior al período del export",
        Availability.NO_SENSOR_DATA: "Sin datos de LibreView",
        Availability.PRESENT: f"{summary.n} medición(es)",
        Availability.ABSENT: "Sin mediciones",
    }[summary.availability]
