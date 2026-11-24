"""Cálculo determinista del estado de SLA de incidentes (ver ADR-002).

- P0/P1 (``operates_24x7=True``): consumen SLA en minutos de reloj.
- P2/P3 (``operates_24x7=False``): solo consumen SLA en horario hábil,
  de lunes a viernes, en la ventana semiabierta [08:00, 18:00) de Bogotá.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone, tzinfo
from typing import Dict, List

from src.models import Incident, SLAEvaluation, SLARule, SeverityLevel

# ---------------------------------------------------------------------------
# Política de SLA
# ---------------------------------------------------------------------------

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

# ---------------------------------------------------------------------------
# Horario hábil
# ---------------------------------------------------------------------------

# Colombia no aplica horario de verano desde 1993, así que un desfase fijo de
# UTC-5 equivale a ZoneInfo("America/Bogota"). Además funciona en Windows sin
# el paquete externo `tzdata`, lo que respeta la regla de cero dependencias.
BUSINESS_TZ: tzinfo = timezone(timedelta(hours=-5), "America/Bogota")
BUSINESS_START = time(8, 0)
BUSINESS_END = time(18, 0)  # ventana semiabierta [08:00, 18:00)
BUSINESS_WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # 0 = lunes ... 4 = viernes

_ZERO = timedelta(0)
_ONE_DAY = timedelta(days=1)
_ONE_MINUTE = timedelta(minutes=1)


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _to_business_tz(moment: datetime) -> datetime:
    """Expresa ``moment`` en hora de negocio.

    Un ``datetime`` ingenuo (sin tzinfo) se interpreta como hora local de
    negocio, igual que hacía el código anterior. Uno con zona horaria se convierte.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        return moment.replace(tzinfo=BUSINESS_TZ)
    return moment.astimezone(BUSINESS_TZ)


def _business_time_between(start: datetime, end: datetime) -> timedelta:
    """Tiempo de [start, end] que cae de lunes a viernes, 08:00-18:00, hora de negocio.

    Recorre cada día calendario, interseca el intervalo con la ventana hábil de
    ese día y acumula ``timedelta`` exactos, sin redondear por día (descarta la
    Opción E del ADR). El costo es O(días abarcados).
    """
    start = _to_business_tz(start)
    end = _to_business_tz(end)

    total = _ZERO
    day = start.date()
    last_day = end.date()
    while day <= last_day:
        if day.weekday() in BUSINESS_WEEKDAYS:
            window_start = datetime.combine(day, BUSINESS_START, tzinfo=BUSINESS_TZ)
            window_end = datetime.combine(day, BUSINESS_END, tzinfo=BUSINESS_TZ)
            overlap = min(end, window_end) - max(start, window_start)
            if overlap > _ZERO:
                total += overlap
        day += _ONE_DAY
    return total


def _elapsed_minutes(rule: SLARule, start: datetime, end: datetime) -> int:
    """Minutos de SLA consumidos según la regla, con una única conversión final."""
    if rule.operates_24x7:
        # P0/P1: el mismo cálculo de reloj que antes, sin cambios.
        delta_seconds = (end - start).total_seconds()
        return int(delta_seconds // 60)
    # P2/P3: división entera exacta entre timedelta, sin aritmética de float.
    return _business_time_between(start, end) // _ONE_MINUTE


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Para P2/P3, ``elapsed_minutes`` y ``remaining_minutes`` se expresan en
    minutos hábiles. Para P0/P1 se expresan en minutos de reloj.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.
            Se ignora si el incidente tiene ``resolved_at``.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.

    Raises:
        ValueError: si la severidad no es válida o el fin es anterior a la creación.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    elapsed_minutes = _elapsed_minutes(rule, incident.created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED"
        and not is_breached
        and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


# ---------------------------------------------------------------------------
# Demostración ejecutable: uv run python -m src.sla_calculator
# ---------------------------------------------------------------------------

_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


@dataclass(frozen=True)
class _DemoCase:
    name: str
    severity: SeverityLevel
    created_at: datetime
    end_time: datetime
    expected_elapsed: int
    expected_breached: bool = False
    expected_escalation: bool = False
    status: str = "OPEN"  # "RESOLVED" usa end_time como resolved_at


def _nov(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Fecha ingenua de noviembre de 2026 en hora de negocio (2026-11-09 es lunes)."""
    return datetime(2026, 11, day, hour, minute, second)


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def _fmt(moment: datetime) -> str:
    pattern = "%d %H:%M:%S" if moment.second else "%d %H:%M"
    suffix = " UTC" if moment.utcoffset() == _ZERO else ""
    return f"{_DIAS[moment.weekday()]} {moment.strftime(pattern)}{suffix}"


def _demo_cases() -> List[_DemoCase]:
    return [
        # --- Básicos ------------------------------------------------------------
        _DemoCase("Mismo día hábil", "P2", _nov(10, 10), _nov(10, 11, 30), 90),
        _DemoCase("Cruce nocturno", "P2", _nov(9, 17), _nov(10, 9), 120),
        # --- Fin de semana: horario hábil vs 24x7 sobre el MISMO intervalo ------
        _DemoCase("Cruce fin de semana (hoy: 3720)", "P2", _nov(6, 17, 30), _nov(9, 7, 30), 30),
        _DemoCase("Mismo intervalo en 24x7", "P0", _nov(6, 17, 30), _nov(9, 7, 30), 3720,
                  expected_breached=True),
        _DemoCase("Íntegro en fin de semana", "P3", _nov(7, 10), _nov(8, 20), 0),
        _DemoCase("24x7 en fin de semana", "P1", _nov(7, 10), _nov(7, 11), 60),
        _DemoCase("Ejemplo lunes 09:00 (vie 16:00)", "P3", _nov(6, 16), _nov(9, 9), 180),
        _DemoCase("Varios días con fin de semana", "P3", _nov(5, 9), _nov(10, 9), 1800,
                  expected_breached=True),
        # --- Creación fuera de horario y fronteras ------------------------------
        _DemoCase("Creado antes de abrir", "P2", _nov(9, 6), _nov(9, 9, 15), 75),
        _DemoCase("Creado tras cierre (hoy: 645, escala)", "P2", _nov(9, 22), _nov(10, 8, 45), 45),
        _DemoCase("Frontera de cierre 18:00", "P2", _nov(9, 18), _nov(9, 18, 30), 0),
        _DemoCase("Frontera de apertura 08:00", "P2", _nov(9, 8), _nov(9, 8, 1), 1),
        _DemoCase("Precisión en segundos", "P2", _nov(9, 17, 59, 30), _nov(10, 8, 0, 30), 1),
        _DemoCase("Entrada con zona UTC", "P2", _utc(9, 22), _utc(9, 23, 30), 60),
        # --- Umbrales P2 (escala >= 360, incumple > 480) ------------------------
        _DemoCase("Umbral: 359 no escala", "P2", _nov(9, 8), _nov(9, 13, 59), 359),
        _DemoCase("Umbral: 360 escala", "P2", _nov(9, 8), _nov(9, 14), 360,
                  expected_escalation=True),
        _DemoCase("Umbral: 480 no incumple", "P2", _nov(9, 8), _nov(9, 16), 480,
                  expected_escalation=True),
        _DemoCase("Umbral: 481 incumple", "P2", _nov(9, 8), _nov(9, 16, 1), 481,
                  expected_breached=True),
        _DemoCase("RESOLVED nunca escala", "P2", _nov(9, 8), _nov(9, 14), 360,
                  status="RESOLVED"),
    ]


def _run_demo() -> int:
    header = (
        f"{'#':>2} {'Caso':<38} {'Sev':<3} {'Inicio':<16} {'Fin':<20} "
        f"{'Reloj':>6} {'SLA':>6} {'Esper.':>6} {'Rest.':>6} {'Esc':<3} {'Inc':<3} Res."
    )
    print("Evaluación de SLA: P0/P1 en reloj, P2/P3 en horario hábil (lun-vie 08:00-18:00)")
    print(header)
    print("-" * len(header))

    failures = 0
    for idx, case in enumerate(_demo_cases(), start=1):
        resolved = case.status == "RESOLVED"
        incident = Incident(
            incident_id=f"DEMO-{idx:02d}",
            title=case.name,
            component="demo",
            severity=case.severity,
            status=case.status,
            created_at=case.created_at,
            resolved_at=case.end_time if resolved else None,
        )
        # Si está resuelto, reference_time se ignora; se pasa uno posterior para demostrarlo.
        reference_time = case.end_time + _ONE_DAY if resolved else case.end_time
        evaluation = evaluate_sla_status(incident, reference_time=reference_time)

        clock_minutes = int((case.end_time - case.created_at).total_seconds() // 60)
        got = (evaluation.elapsed_minutes, evaluation.is_breached, evaluation.requires_escalation)
        expected = (case.expected_elapsed, case.expected_breached, case.expected_escalation)
        ok = got == expected
        # Propiedad: los minutos hábiles nunca superan los de reloj.
        if not get_sla_rule_for_severity(case.severity).operates_24x7:
            ok = ok and evaluation.elapsed_minutes <= clock_minutes
        failures += not ok

        print(
            f"{idx:>2} {case.name:<38} {case.severity:<3} {_fmt(case.created_at):<16} "
            f"{_fmt(case.end_time):<20} {clock_minutes:>6} {evaluation.elapsed_minutes:>6} "
            f"{case.expected_elapsed:>6} {evaluation.remaining_minutes:>6} "
            f"{'si' if evaluation.requires_escalation else 'no':<3} "
            f"{'si' if evaluation.is_breached else 'no':<3} {'OK' if ok else 'FALLO'}"
        )

    # Caso de error: el fin es anterior a la creación.
    bad = Incident(
        incident_id="DEMO-ERR", title="Fin anterior a creación", component="demo",
        severity="P2", status="OPEN", created_at=_nov(10, 10),
    )
    try:
        evaluate_sla_status(bad, reference_time=_nov(10, 9))
        print("ERR Fin anterior a creación: no lanzó ValueError -> FALLO")
        failures += 1
    except ValueError:
        print("ERR Fin anterior a creación: lanza ValueError -> OK")

    print("-" * len(header))
    print("Todos los casos OK." if failures == 0 else f"{failures} caso(s) con FALLO.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_demo())