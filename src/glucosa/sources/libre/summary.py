"""Resumen legible de una importación: solo conteos, sin valores ni datos personales."""

from glucosa.sources.libre.csv_format import REASON_LABELS
from glucosa.sources.libre.models import ImportSummary


def _period(summary: ImportSummary) -> str:
    if summary.period_start is None:
        return "sin lecturas de glucosa"
    return f"{summary.period_start.replace('T', ' ')} → {summary.period_end.replace('T', ' ')}"


def render_summary(summary: ImportSummary) -> str:
    events = summary.other_events
    lines = [
        "== RESUMEN DE LA IMPORTACIÓN DE LIBREVIEW ==",
        f"Archivo: {summary.file_name} ({summary.file_bytes:,} bytes)".replace(",", "."),
        f"Período de datos: {_period(summary)}",
        f"Filas de datos: {summary.rows_total}",
        f"Lecturas históricas del sensor: {summary.historic_rows}",
        f"Escaneos: {summary.scan_rows}",
        "Otros eventos no consolidados: "
        f"alimentos {events['alimento']}, notas {events['nota']}, otros {events['otros']}",
        f"Nuevos: {summary.new} (historial {summary.new_historic}, escaneos {summary.new_scans})",
        f"Repetidos: {summary.repeated}",
        f"Inválidos: {summary.invalid}",
    ]
    for reason, count in sorted(summary.invalid_by_reason.items()):
        lines.append(
            f"  · {reason.upper() if reason in ('hi', 'lo') else reason}: {count} — "
            f"{REASON_LABELS.get(reason, reason)}"
        )
    lines += [
        f"Conflictos: {summary.conflicts} claves ({summary.rows_in_conflict} filas), "
        "no consolidados ni sobrescritos",
        f"Total consolidado: {summary.total_consolidated} "
        f"(historial {summary.total_historic}, escaneos {summary.total_scans})",
        f"Última importación: {summary.last_import_utc:%Y-%m-%d %H:%M} UTC",
    ]
    if summary.same_file_seen_before:
        lines.append("Nota: este mismo archivo ya se había importado antes; no se duplicó nada.")
    return "\n".join(lines) + "\n"
