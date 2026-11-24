"""Aceptación BDD — specs/001-triage-endpoint-manual.md (1 escenario = 1 prueba)."""

from __future__ import annotations

import json

import pytest

from src.adapters.inbound.cli import app as cli_app
from tests.conftest import LOCKED_ACCOUNT_TODAY, PAYMENTS_502_OUTAGE


def test_bdd_s1_caida_critica_502_en_pasarela_de_pagos_es_p0(client):
    # Given un reporte de caída HTTP 502 que impide cobrar en la pasarela de pagos
    body = {"incident_id": "INC-1001", "raw_text": PAYMENTS_502_OUTAGE}
    # When soporte lo envía al servicio de triaje
    response = client.post("/api/v1/incidents/triage", json=body)
    # Then se clasifica P0 para Backend-Core con la clave de duplicados de la caída 502
    assert response.status_code == 200
    data = response.json()
    assert data["severity"] == "P0"
    assert data["component"] == "payments-gateway"
    assert data["recommended_team"] == "Backend-Core"
    assert data["duplicate_group_key"] == "payments-gateway:http-502-outage"
    assert set(data) >= {"symptom_category", "impact_scope", "rationale", "consistency_ratio"}


def test_bdd_s2_cuenta_individual_bloqueada_con_hoy_no_es_falso_p0(client):
    # Given un usuario con su cuenta bloqueada que insiste en que lo necesita "hoy"
    body = {"incident_id": "INC-1002", "raw_text": LOCKED_ACCOUNT_TODAY}
    # When se envía al triaje
    response = client.post("/api/v1/incidents/triage", json=body)
    # Then la urgencia percibida no eleva la severidad: P2 para Security-IAM
    assert response.status_code == 200
    data = response.json()
    assert data["severity"] == "P2"
    assert data["recommended_team"] == "Security-IAM"
    assert "hoy" in data["rationale"]


@pytest.mark.parametrize(
    "body",
    [
        {"incident_id": "INC-2000", "raw_text": "   "},
        {"incident_id": "", "raw_text": "Error 502 en pagos"},
        {"incident_id": "   ", "raw_text": "Error 502 en pagos"},
    ],
)
def test_bdd_s3_entradas_vacias_o_solo_espacios_son_rechazadas(client, body):
    # Given un reporte con identificador o texto vacío / solo espacios
    # When se envía al triaje
    response = client.post("/api/v1/incidents/triage", json=body)
    # Then se rechaza como entidad no procesable
    assert response.status_code == 422


def test_bdd_s4_paridad_cli_triage(cli_runner):
    # Given el mismo reporte de caída 502 usado por la API
    # When soporte lo clasifica desde la terminal
    result = cli_runner.invoke(
        cli_app, ["triage", "--incident-id", "INC-1001", "--raw-text", PAYMENTS_502_OUTAGE]
    )
    # Then obtiene JSON válido equivalente al de la API y código de salida 0
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["severity"] == "P0"
    assert data["recommended_team"] == "Backend-Core"
    assert data["duplicate_group_key"] == "payments-gateway:http-502-outage"


def test_bdd_s4b_cli_triage_rechaza_texto_vacio(cli_runner):
    # Given un texto compuesto solo por espacios / When se ejecuta el CLI / Then sale con código 1
    result = cli_runner.invoke(cli_app, ["triage", "--incident-id", "INC-1", "--raw-text", "   "])
    assert result.exit_code == 1
