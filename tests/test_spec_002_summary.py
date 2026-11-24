"""Aceptación BDD — specs/002-active-incidents-summary/spec.md."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident

REFERENCE = "2026-11-09T12:00:00"  # lunes


def _incident(incident_id, component, severity, status, created_at):
    return Incident(
        incident_id=incident_id,
        title=f"Incidente {incident_id} en {component}",
        component=component,
        severity=severity,
        status=status,
        created_at=datetime.fromisoformat(created_at),
    )


@pytest.fixture
def seeded(repository):
    """Given un tablero con incidentes activos, uno incumplido y uno resuelto."""
    for inc in (
        _incident("INC-A1", "payments-gateway", "P0", "OPEN", "2026-11-09T10:00:00"),  # 120 > 60 incumple
        _incident("INC-A2", "payments-gateway", "P1", "IN_PROGRESS", "2026-11-09T11:00:00"),  # 60/240
        _incident("INC-A3", "reporting-api", "P2", "OPEN", "2026-11-09T08:00:00"),  # 240/480
        _incident("INC-R1", "payments-gateway", "P0", "RESOLVED", "2026-11-09T09:00:00"),
    ):
        repository.save_incident(inc)
    return repository


def test_bdd_s1_resumen_global_excluye_resueltos(client, seeded):
    # When Operaciones consulta el resumen global en un instante de referencia
    response = client.get("/api/v1/incidents/summary", params={"reference_time": REFERENCE})
    # Then ve solo OPEN/IN_PROGRESS, cuántos incumplieron SLA y el detalle de cada uno
    assert response.status_code == 200
    data = response.json()
    assert data["total_active"] == 3
    assert data["breached_count"] == 1
    ids = [i["incident_id"] for i in data["incidents"]]
    assert "INC-R1" not in ids
    first = next(i for i in data["incidents"] if i["incident_id"] == "INC-A1")
    assert first == {
        "incident_id": "INC-A1",
        "title": "Incidente INC-A1 en payments-gateway",
        "component": "payments-gateway",
        "severity": "P0",
        "status": "OPEN",
        "elapsed_minutes": 120,
        "is_breached": True,
        "requires_escalation": False,
    }


def test_bdd_s2_resumen_filtrado_por_componente(client, seeded):
    # When filtra por el componente reporting-api
    response = client.get(
        "/api/v1/incidents/summary", params={"component": "reporting-api", "reference_time": REFERENCE}
    )
    # Then solo ve los incidentes activos de ese componente
    data = response.json()
    assert response.status_code == 200
    assert data["total_active"] == 1
    assert data["breached_count"] == 0
    assert [i["incident_id"] for i in data["incidents"]] == ["INC-A3"]


def test_bdd_s3_sin_incidentes_activos_devuelve_resumen_vacio(client, seeded):
    # Given un componente sin incidentes activos / When se consulta / Then resumen vacío válido
    response = client.get("/api/v1/incidents/summary", params={"component": "frontend-ui"})
    assert response.status_code == 200
    data = response.json()
    assert (data["total_active"], data["breached_count"], data["incidents"]) == (0, 0, [])


def test_bdd_s4_resumen_equivalente_por_cli(cli_runner, cli_database):
    # Given incidentes activos en la base configurada por DATABASE_URL
    repo = SQLiteIncidentRepository(cli_database.removeprefix("sqlite:///"))
    repo.save_incident(_incident("INC-C1", "payments-gateway", "P0", "OPEN", "2026-11-09T10:00:00"))
    repo.save_incident(_incident("INC-C2", "reporting-api", "P2", "OPEN", "2026-11-09T08:00:00"))
    # When soporte consulta el resumen filtrado desde la terminal
    result = cli_runner.invoke(
        cli_app, ["summary", "--component", "payments-gateway", "--reference-time", REFERENCE]
    )
    # Then recibe el mismo contrato JSON que la API
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["total_active"] == 1 and data["breached_count"] == 1
    assert data["incidents"][0]["incident_id"] == "INC-C1"


def test_sqlite_repository_cumple_incident_repository_port(repository):
    assert isinstance(repository, IncidentRepositoryPort)
