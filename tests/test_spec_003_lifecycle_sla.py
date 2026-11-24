"""Aceptación BDD — specs/003-incident-lifecycle-sla/spec.md."""

from __future__ import annotations

import json
import re

from src.adapters.inbound.cli import app as cli_app
from tests.conftest import (
    LOCKED_ACCOUNT_TODAY,
    PAYMENTS_502_OUTAGE,
    PAYMENTS_502_RECURRENCE,
    SLOW_DASHBOARD,
)


def test_bdd_s1_registro_inicial_sin_duplicados(client):
    # Given no hay incidentes registrados
    # When llega un reporte nuevo sin identificador ni fecha
    response = client.post(
        "/api/v1/incidents", json={"title": "Caída de pagos", "raw_text": PAYMENTS_502_OUTAGE}
    )
    # Then se registra (201) con su clasificación completa y sin duplicados
    assert response.status_code == 201
    data = response.json()
    assert re.fullmatch(r"INC-[0-9A-F]{8}", data["incident_id"])
    assert data["status"] == "OPEN"
    assert data["severity"] == "P0" and data["recommended_team"] == "Backend-Core"
    assert data["duplicate_group_key"] == "payments-gateway:http-502-outage"
    assert data["is_duplicate"] is False and data["duplicate_of"] == []


def test_bdd_s2_detecta_duplicado_abierto_e_ignora_resueltos(client):
    # Given una caída 502 ya resuelta y otra todavía abierta en la pasarela de pagos
    client.post("/api/v1/incidents", json={
        "incident_id": "INC-OLD", "title": "Caída antigua", "raw_text": PAYMENTS_502_OUTAGE,
        "status": "RESOLVED",
    })
    client.post("/api/v1/incidents", json={
        "incident_id": "INC-1001", "title": "Caída de pagos", "raw_text": PAYMENTS_502_OUTAGE,
    })
    # When llega un nuevo reporte equivalente
    response = client.post("/api/v1/incidents", json={
        "incident_id": "INC-1006", "title": "Otra vez cayó", "raw_text": PAYMENTS_502_RECURRENCE,
    })
    # Then se registra (201) y se avisa que duplica solo al incidente abierto
    assert response.status_code == 201
    data = response.json()
    assert data["is_duplicate"] is True
    assert data["duplicate_of"] == ["INC-1001"]


def test_bdd_s3_auditoria_sla_en_horario_habil(client):
    # Given un P2 registrado el viernes 2026-11-06 a las 17:00
    created = client.post("/api/v1/incidents", json={
        "incident_id": "INC-2002", "title": "Cuenta bloqueada", "raw_text": LOCKED_ACCOUNT_TODAY,
        "created_at": "2026-11-06T17:00:00",
    })
    assert created.json()["severity"] == "P2"
    # When se audita su SLA el lunes 2026-11-09 a las 09:00
    response = client.get(
        "/api/v1/incidents/INC-2002/sla", params={"reference_time": "2026-11-09T09:00:00"}
    )
    # Then solo cuentan los minutos hábiles (1 h viernes + 1 h lunes)
    assert response.status_code == 200
    assert response.json() == {
        "incident_id": "INC-2002",
        "severity": "P2",
        "elapsed_minutes": 120,
        "allowed_minutes": 480,
        "remaining_minutes": 360,
        "is_breached": False,
        "requires_escalation": False,
    }


def test_bdd_s4_sla_de_incidente_inexistente_o_referencia_anterior(client):
    # Given un incidente registrado el lunes a las 10:00
    client.post("/api/v1/incidents", json={
        "incident_id": "INC-3003", "title": "Dashboard lento", "raw_text": SLOW_DASHBOARD,
        "created_at": "2026-11-09T10:00:00",
    })
    # When se audita un identificador inexistente / Then 404
    assert client.get("/api/v1/incidents/INC-NOPE/sla").status_code == 404
    # When se audita con una referencia anterior a la creación / Then 422
    response = client.get(
        "/api/v1/incidents/INC-3003/sla", params={"reference_time": "2026-11-09T09:00:00"}
    )
    assert response.status_code == 422


def test_bdd_s4b_registro_rechaza_campos_vacios(client):
    # Given título o texto vacío / When se intenta registrar / Then 422
    assert client.post("/api/v1/incidents", json={"title": "  ", "raw_text": "x"}).status_code == 422
    assert client.post("/api/v1/incidents", json={"title": "x", "raw_text": ""}).status_code == 422


def test_bdd_s5_operacion_equivalente_por_cli(cli_runner, cli_database):
    # Given la base configurada por DATABASE_URL
    # When soporte registra dos reportes equivalentes y audita el SLA desde la terminal
    first = cli_runner.invoke(cli_app, [
        "create", "--incident-id", "INC-2002", "--title", "Cuenta bloqueada",
        "--raw-text", LOCKED_ACCOUNT_TODAY, "--created-at", "2026-11-06T17:00:00",
    ])
    second = cli_runner.invoke(cli_app, [
        "create", "--title", "Cuenta bloqueada otra vez", "--raw-text", LOCKED_ACCOUNT_TODAY,
    ])
    sla = cli_runner.invoke(cli_app, [
        "sla", "--incident-id", "INC-2002", "--reference-time", "2026-11-09T09:00:00",
    ])
    missing = cli_runner.invoke(cli_app, ["sla", "--incident-id", "INC-NOPE"])
    empty = cli_runner.invoke(cli_app, ["create", "--title", " ", "--raw-text", "x"])
    # Then obtiene los mismos contratos JSON y códigos de salida que la API
    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["is_duplicate"] is False
    assert second.exit_code == 0
    assert json.loads(second.stdout)["duplicate_of"] == ["INC-2002"]
    assert sla.exit_code == 0
    assert json.loads(sla.stdout)["elapsed_minutes"] == 120
    assert missing.exit_code == 1
    assert empty.exit_code == 1
