"""Adaptador primario CLI (Typer). Mismos casos de uso y mismos contratos JSON que la API.

Uso:  uv run python -m src.adapters.inbound.cli --help
La persistencia se selecciona con DATABASE_URL (por defecto sqlite:///:memory:).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

import typer
from pydantic import BaseModel

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    HealthResponse,
    IncidentCreatedResponse,
    SLAEvaluationResponse,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentNotFoundError, IncidentService, ValidationError

app = typer.Typer(help="IncidentOps CLI: triaje, resumen, ciclo de vida, SLA y salud.", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """IncidentOps CLI."""


def _service() -> IncidentService:
    return IncidentService(create_repository())


def _emit(model: BaseModel) -> None:
    payload: Dict[str, Any] = model.model_dump(mode="json")
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str) -> None:
    typer.echo(json.dumps({"error": message}, ensure_ascii=False), err=True)
    raise typer.Exit(code=1)


def _parse_dt(value: Optional[str], name: str) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _fail(f"'{name}' debe estar en formato ISO 8601 (p. ej. 2026-11-09T09:00:00).")
    return None  # pragma: no cover


@app.command()
def triage(
    incident_id: str = typer.Option(..., "--incident-id", help="Identificador del reporte."),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto crudo del reporte."),
) -> None:
    """Clasifica un reporte sin persistirlo (Hito 001)."""
    try:
        _emit(TriageResponse.from_result(IncidentService().triage_incident(incident_id, raw_text)))
    except ValidationError as exc:
        _fail(str(exc))


@app.command()
def summary(
    component: Optional[str] = typer.Option(None, "--component", help="Filtra por componente."),
    reference_time: Optional[str] = typer.Option(None, "--reference-time", help="Instante ISO 8601."),
) -> None:
    """Resumen de incidentes activos y SLA incumplidos (Hito 002)."""
    ref = _parse_dt(reference_time, "reference-time")
    _emit(ActiveIncidentsSummaryResponse.from_summary(_service().get_active_incidents_summary(component, ref)))


@app.command()
def create(
    title: str = typer.Option(..., "--title", help="Título del incidente."),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto crudo del reporte."),
    incident_id: Optional[str] = typer.Option(None, "--incident-id", help="Opcional; INC-<HEX8> si se omite."),
    created_at: Optional[str] = typer.Option(None, "--created-at", help="Instante ISO 8601; ahora si se omite."),
    status: str = typer.Option("OPEN", "--status", help="OPEN | IN_PROGRESS | ESCALATION_REQUIRED | RESOLVED"),
) -> None:
    """Registra un incidente y avisa si ya hay otro equivalente abierto (Hito 003)."""
    created = _parse_dt(created_at, "created-at")
    try:
        registration = _service().create_incident(title, raw_text, incident_id, created, status)
    except ValidationError as exc:
        _fail(str(exc))
    else:
        _emit(IncidentCreatedResponse.from_registration(registration))


@app.command()
def sla(
    incident_id: str = typer.Option(..., "--incident-id", help="Incidente a auditar."),
    reference_time: Optional[str] = typer.Option(None, "--reference-time", help="Instante ISO 8601."),
) -> None:
    """Audita el SLA de un incidente registrado (Hito 003)."""
    ref = _parse_dt(reference_time, "reference-time")
    try:
        evaluation = _service().evaluate_incident_sla(incident_id, ref)
    except (ValidationError, IncidentNotFoundError) as exc:
        _fail(str(exc))
    else:
        _emit(SLAEvaluationResponse.from_evaluation(evaluation))


@app.command()
def health() -> None:
    """Chequeo real de conectividad con la base configurada (Hito 004)."""
    healthy = _service().check_health()
    _emit(HealthResponse.from_flag(healthy))
    if not healthy:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
