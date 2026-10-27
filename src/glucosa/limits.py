"""Límites compartidos y neutrales (no pertenecen a ninguna fuente de datos)."""

# Rango de glucosa (mg/dL) que valida la app Android al registrar y que se usa como rango
# plausible para cualquier fuente.
GLUCOSE_RANGE: tuple[int, int] = (20, 600)
