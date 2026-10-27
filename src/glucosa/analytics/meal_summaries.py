"""Indicadores de Alimentación: conteos y promedios por tipo, día, horario y alimento.

Reglas (aprobadas en la Etapa D1):

* Los días sin registro **no** son días sin comer: «sin registro» y «sin comida» no se
  confunden. Por eso hay tres denominadores rotulados: días con registro, días del período
  y días desde el primer registro.
* El horario habitual es la **mediana** de la hora declarada; solo se informa con un mínimo
  de comidas.
* Los alimentos se agrupan por nombre normalizado (ver ``models/foods``); el texto original
  se conserva.
* Las **cantidades son texto libre y nunca se suman**, promedian ni convierten.
* Este módulo no conoce la glucosa: la asociación temporal con glucosa es una etapa posterior.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, median

from glucosa.analytics.glucose_filters import Period
from glucosa.analytics.meal_view import NO_TYPE_LABEL, TYPE_LABELS, MealView, filter_meals
from glucosa.models.foods import normalize_food_name
from glucosa.models.records import MealType

MIN_MEALS_FOR_SUMMARY = 5  # menos comidas que esto: «datos insuficientes»
DAY_START_MINUTE = (
    4 * 60
)  # la «jornada» empieza a las 04:00 para que las cenas tardías no se partan
MINUTES_PER_DAY = 24 * 60
_TYPE_ORDER: tuple[MealType | None, ...] = (*MealType, None)


# ------------------------------------------------------------------ resumen general
@dataclass(frozen=True)
class MealSummary:
    meals: int
    days_with_records: int
    days_in_period: int
    meals_per_active_day: float | None  # sobre días CON registro
    meals_per_period_day: float  # sobre todos los días del período
    median_per_active_day: float | None
    min_per_active_day: int | None
    max_per_active_day: int | None
    first_record_day: (
        date | None
    )  # primer registro disponible (la sincronización no es retroactiva)
    days_since_first_record: int | None  # días del período desde ese primer registro
    meals_per_since_first_record_day: float | None
    items_total: int
    items_per_meal_mean: float | None
    items_per_meal_median: float | None
    meals_without_items: int
    meals_with_unknown_type: int


def _days_since(first: date | None, period: Period) -> int | None:
    if first is None:
        return None
    start = max(first, period.first_day)
    return max(0, (period.last_day - start).days + 1)


def summarize_meals(meals: Sequence[MealView], period: Period) -> MealSummary:
    """Indicadores de las comidas del período. ``meals`` puede traer comidas de otros períodos."""
    in_period = filter_meals(meals, period=period)
    per_day = Counter(m.local_date for m in in_period)
    days_in_period = (period.last_day - period.first_day).days + 1
    first_record = min((m.local_date for m in meals), default=None)
    since_first = _days_since(first_record, period)
    item_counts = [m.item_count for m in in_period]
    return MealSummary(
        meals=len(in_period),
        days_with_records=len(per_day),
        days_in_period=days_in_period,
        meals_per_active_day=len(in_period) / len(per_day) if per_day else None,
        meals_per_period_day=len(in_period) / days_in_period,
        median_per_active_day=median(per_day.values()) if per_day else None,
        min_per_active_day=min(per_day.values()) if per_day else None,
        max_per_active_day=max(per_day.values()) if per_day else None,
        first_record_day=first_record,
        days_since_first_record=since_first,
        meals_per_since_first_record_day=(len(in_period) / since_first) if since_first else None,
        items_total=sum(item_counts),
        items_per_meal_mean=mean(item_counts) if item_counts else None,
        items_per_meal_median=median(item_counts) if item_counts else None,
        meals_without_items=sum(count == 0 for count in item_counts),
        meals_with_unknown_type=sum(m.type is None for m in in_period),
    )


# ------------------------------------------------------------- comidas por día (rotulado)
PRIMARY_PER_DAY_LABEL = "Comidas por día con registros"
PERIOD_PER_DAY_LABEL = "Comidas por día calendario del período"
SINCE_FIRST_PER_DAY_LABEL = "Comidas por día desde el primer registro"
_BEFORE_SYNC_NOTE = "El período termina antes del primer registro sincronizado: no hay datos."
_PARTIAL_SYNC_NOTE = (
    "El período incluye días anteriores al primer registro sincronizado (sin datos)."
)
_NO_MEALS_NOTE = "Aún no hay comidas registradas."


@dataclass(frozen=True)
class PerDayIndicator:
    label: str
    value: float | None  # None = no definido (nunca se muestra como 0)
    days: int | None  # días por los que se divide
    primary: bool
    note: str | None = None


def per_day_indicators(summary: MealSummary) -> list[PerDayIndicator]:
    """Comidas por día: el principal sobre días CON registro y dos secundarios rotulados."""
    synced_days = summary.days_since_first_record
    period_note = None
    period_value: float | None = summary.meals_per_period_day
    if summary.first_record_day is None:
        period_value, period_note = None, _NO_MEALS_NOTE
    elif not synced_days:
        period_value, period_note = None, _BEFORE_SYNC_NOTE
    elif synced_days < summary.days_in_period:
        period_note = _PARTIAL_SYNC_NOTE
    return [
        PerDayIndicator(
            PRIMARY_PER_DAY_LABEL,
            summary.meals_per_active_day,
            summary.days_with_records,
            primary=True,
        ),
        PerDayIndicator(
            PERIOD_PER_DAY_LABEL,
            period_value,
            summary.days_in_period,
            primary=False,
            note=period_note,
        ),
        PerDayIndicator(
            SINCE_FIRST_PER_DAY_LABEL,
            summary.meals_per_since_first_record_day,
            synced_days,
            primary=False,
            note=_BEFORE_SYNC_NOTE if synced_days == 0 else None,
        ),
    ]


# ------------------------------------------------------------------------- por tipo
@dataclass(frozen=True)
class TypeCount:
    type: MealType | None
    label: str
    meals: int
    share: float | None


def type_counts(meals: Sequence[MealView]) -> list[TypeCount]:
    counts = Counter(m.type for m in meals)
    total = len(meals)
    return [
        TypeCount(
            kind,
            NO_TYPE_LABEL if kind is None else TYPE_LABELS[kind],
            counts.get(kind, 0),
            counts.get(kind, 0) / total if total else None,
        )
        for kind in _TYPE_ORDER
    ]


# --------------------------------------------------------------------------- por día
@dataclass(frozen=True)
class DayCount:
    day: date
    meals: int

    @property
    def has_records(self) -> bool:
        return self.meals > 0


def meals_by_day(meals: Sequence[MealView], period: Period) -> list[DayCount]:
    """Un renglón por cada día local del período; 0 significa «sin registro», no «no comió»."""
    counts = Counter(m.local_date for m in filter_meals(meals, period=period))
    days = (period.last_day - period.first_day).days + 1
    return [
        DayCount(
            period.first_day + timedelta(days=offset),
            counts.get(period.first_day + timedelta(days=offset), 0),
        )
        for offset in range(days)
    ]


@dataclass(frozen=True)
class WeekdayCounts:
    by_weekday: tuple[int, ...]  # lunes … domingo

    @property
    def weekend(self) -> int:
        return self.by_weekday[5] + self.by_weekday[6]

    @property
    def weekday(self) -> int:
        return sum(self.by_weekday[:5])


def weekday_counts(meals: Sequence[MealView]) -> WeekdayCounts:
    counts = Counter(m.weekday for m in meals)
    return WeekdayCounts(tuple(counts.get(day, 0) for day in range(7)))


# ------------------------------------------------------------------------- horarios
@dataclass(frozen=True)
class HourBin:
    hour: int
    meals: int


def hour_histogram(meals: Sequence[MealView]) -> list[HourBin]:
    counts = Counter(m.hour for m in meals)
    return [HourBin(hour, counts.get(hour, 0)) for hour in range(24)]


@dataclass(frozen=True)
class TypeTime:
    type: MealType | None
    label: str
    meals: int
    sufficient: bool
    median_minute: int | None  # hora local como minutos desde medianoche
    earliest_minute: int | None
    latest_minute: int | None


def _shift(minute: int) -> int:
    return (minute - DAY_START_MINUTE) % MINUTES_PER_DAY


def _unshift(shifted: float) -> int:
    return (round(shifted) + DAY_START_MINUTE) % MINUTES_PER_DAY


def time_of_day_by_type(
    meals: Sequence[MealView], min_meals: int = MIN_MEALS_FOR_SUMMARY
) -> list[TypeTime]:
    """Hora habitual (mediana de la declarada) por tipo; bajo ``min_meals``: insuficiente."""
    rows = []
    for kind in _TYPE_ORDER:
        shifted = sorted(_shift(m.minute_of_day) for m in meals if m.type is kind)
        enough = len(shifted) >= max(1, min_meals)
        rows.append(
            TypeTime(
                type=kind,
                label=NO_TYPE_LABEL if kind is None else TYPE_LABELS[kind],
                meals=len(shifted),
                sufficient=enough,
                median_minute=_unshift(median(shifted)) if enough else None,
                earliest_minute=_unshift(shifted[0]) if enough else None,
                latest_minute=_unshift(shifted[-1]) if enough else None,
            )
        )
    return rows


# ------------------------------------------------------------------------ alimentos
@dataclass(frozen=True)
class FoodRank:
    normalized: str
    display_name: str  # la escritura original más frecuente
    meals: int  # comidas que contienen el alimento
    occurrences: int  # veces que aparece (puede ser > comidas si se repite dentro de una)
    share_of_meals: float


@dataclass(frozen=True)
class FoodDiversity:
    distinct_foods: int
    seen_once: int  # alimentos presentes en una sola comida
    items: int


def _clean(text: str) -> str:
    return " ".join(text.split())


def food_ranking(meals: Sequence[MealView], top: int | None = None) -> list[FoodRank]:
    """Ranking por número de comidas que contienen el alimento (empates: orden alfabético)."""
    meals_with: Counter[str] = Counter()
    occurrences: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for meal in meals:
        for key in meal.normalized_foods:
            meals_with[key] += 1
        for item in meal.items:
            if not item.normalized:
                continue
            occurrences[item.normalized] += 1
            spellings.setdefault(item.normalized, Counter())[_clean(item.name)] += 1
    total = len(meals)
    ranking = [
        FoodRank(
            normalized=key,
            display_name=spellings[key].most_common(1)[0][0],
            meals=meals_with[key],
            occurrences=occurrences[key],
            share_of_meals=meals_with[key] / total,
        )
        for key in meals_with
    ]
    ranking.sort(key=lambda r: (-r.meals, -r.occurrences, r.normalized))
    return ranking if top is None else ranking[:top]


def food_diversity(meals: Sequence[MealView]) -> FoodDiversity:
    ranking = food_ranking(meals)
    return FoodDiversity(
        distinct_foods=len(ranking),
        seen_once=sum(r.meals == 1 for r in ranking),
        items=sum(meal.item_count for meal in meals),
    )


def most_common_quantity(meals: Sequence[MealView], food: str) -> tuple[str, int] | None:
    """Cantidad (texto) más repetida de un alimento; empate: la más reciente. Sin interpretar."""
    key = normalize_food_name(food)
    counts: Counter[str] = Counter()
    last_seen: dict[str, int] = {}
    position = 0
    for meal in meals:
        for item in meal.items:
            text = _clean(item.quantity)
            if item.normalized == key and text:
                counts[text] += 1
                last_seen[text] = position
                position += 1
    if not counts:
        return None
    best = max(counts, key=lambda text: (counts[text], last_seen[text]))
    return best, counts[best]
