"""Secciones de la aplicación y la fase del plan en que se implementa cada una."""

PAGES: tuple[str, ...] = (
    "Dashboard general",
    "Glucosa",
    "Alimentación",
    "Medicamentos",
    "Biometría",
    "Configuración",
)

PLANNED_PHASE: dict[str, str] = {
    "Dashboard general": "Fase 4–6",
    "Glucosa": "Fase 4 · Etapa C (disponible)",
    "Alimentación": "Etapa D4 (disponible)",
    "Medicamentos": "Fase 5",
    "Biometría": "Fase 5",
    "Configuración": "Fase 3",
}
