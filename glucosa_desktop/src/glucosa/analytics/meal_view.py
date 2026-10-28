"""Vista de comidas para el análisis (lógica pura, sin Streamlit ni glucosa).

Cada comida se presenta con su hora local de Chile, el tipo **declarado** (nunca se corrige
ni se infiere de la hora) y sus alimentos con el texto original intacto más un nombre
normalizado solo para agrupar. ``eaten_at`` es el instante en que se guardó el registro: no
se asume que sea la hora real de comer.
"""

from collections.abc import Iterable, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime

from glucosa.analytics.glucose_filters import Period
from glucosa.data.timeutil import to_santiago
from glucosa.models.foods import normalize_food_name
from glucosa.models.records import MealRecord, MealType

NO_TYPE_LABEL = "Tipo desconocido"
TYPE_LABELS: dict[MealType, str] = {kind: kind.label for kind in MealType}


@dataclass(frozen=True)
class MealItemView:
    name: str  # texto original, sin modificar
    quantity: str  # texto libre original: nunca se interpreta ni se suma
    normalized: str  # solo para agrupar


@dataclass(frozen=True)
class MealView:
    uuid: str
    type: MealType | None
    eaten_at: datetime
    local_date: date
    minute_of_day: int  # hora de pared de Chile, 0–1439
    weekday: int  # lunes = 0 … domingo = 6
    comment: str | None
    items: tuple[MealItemView, ...]

    @property
    def hour(self) -> int:
        return self.minute_of_day // 60

    @property
    def type_label(self) -> str:
        return NO_TYPE_LABEL if self.type is None else TYPE_LABELS[self.type]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def normalized_foods(self) -> frozenset[str]:
        return frozenset(item.normalized for item in self.items if item.normalized)


def _view(record: MealRecord) -> MealView:
    local = to_santiago(record.eaten_at)
    return MealView(
        uuid=record.uuid,
        type=record.type,
        eaten_at=record.eaten_at,
        local_date=local.date(),
        minute_of_day=local.hour * 60 + local.minute,
        weekday=local.weekday(),
        comment=record.comment,
        items=tuple(
            MealItemView(i.food_name, i.quantity, normalize_food_name(i.food_name))
            for i in record.items
        ),
    )


def meal_views(records: Iterable[MealRecord]) -> list[MealView]:
    """Todas las comidas en orden cronológico; no se descarta ni se modifica ninguna."""
    return sorted((_view(r) for r in records), key=lambda v: (v.eaten_at, v.uuid))


def filter_meals(
    meals: Sequence[MealView],
    period: Period | None = None,
    types: Set[MealType | None] | None = None,
    foods: Set[str] | None = None,
) -> list[MealView]:
    """Filtros de POBLACIÓN. ``None`` = sin filtrar; un conjunto vacío = ninguna comida.

    * período: ``[inicio, fin)`` en UTC (días locales de Chile, igual que Glucosa);
    * tipos: ``None`` dentro del conjunto representa «tipo desconocido»;
    * alimentos: cumple si contiene **alguno** de los elegidos (O), por nombre normalizado;
    * criterios distintos se combinan con Y.
    """
    wanted = None if foods is None else {normalize_food_name(f) for f in foods}
    kept = []
    for meal in meals:
        if period is not None and not period.start <= meal.eaten_at < period.end:
            continue
        if types is not None and meal.type not in types:
            continue
        if wanted is not None and not (meal.normalized_foods & wanted):
            continue
        kept.append(meal)
    return kept
