"""Aceptación BDD — specs/004-postgres-container-runtime/spec.md."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident

ROOT = Path(__file__).resolve().parent.parent


class UnavailableRepository:
    """Doble de prueba: cumple el puerto pero la base no responde."""

    def save_incident(self, incident: Incident) -> None:  # pragma: no cover
        raise ConnectionError

    def get_incident(self, incident_id: str) -> Optional[Incident]:  # pragma: no cover
        raise ConnectionError

    def find_open_duplicates(self, duplicate_group_key, exclude_incident_id=None) -> List[Incident]:  # pragma: no cover
        raise ConnectionError

    def list_active_incidents(self, component=None) -> List[Incident]:  # pragma: no cover
        raise ConnectionError

    def check_health(self) -> bool:
        return False


def test_bdd_s1_health_operativo_con_select_1_real(client):
    # Given una base de datos configurada y disponible
    # When la plataforma consulta el chequeo de salud
    response = client.get("/health")
    # Then responde 200 con la base conectada
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_bdd_s1b_health_por_cli(cli_runner, cli_database):
    # When soporte ejecuta el chequeo desde la terminal / Then JSON ok y código 0
    result = cli_runner.invoke(cli_app, ["health"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"status": "ok", "database": "connected"}


def test_bdd_s2_health_ante_fallo_de_conectividad_responde_503():
    # Given un adaptador de persistencia que no logra conectar
    client = TestClient(create_app(IncidentService(UnavailableRepository())))
    # When se consulta el chequeo de salud
    response = client.get("/health")
    # Then responde 503 indicando la base no disponible
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_bdd_s2b_health_cli_falla_con_postgres_inalcanzable(cli_runner, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://incidentops:x@127.0.0.1:1/incidentops")
    result = cli_runner.invoke(cli_app, ["health"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"status": "error", "database": "unavailable"}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://incidentops:secret@db:5432/incidentops", PostgresIncidentRepository),
        ("postgres://incidentops:secret@db:5432/incidentops", PostgresIncidentRepository),
        ("sqlite:///:memory:", SQLiteIncidentRepository),
        ("", SQLiteIncidentRepository),
    ],
)
def test_bdd_s3_seleccion_transparente_por_database_url(url, expected, monkeypatch):
    # Given DATABASE_URL con un esquema postgresql://, sqlite:/// o ausente
    monkeypatch.setenv("DATABASE_URL", url)
    # When se construye la persistencia
    repo = create_repository()
    # Then se elige el adaptador correcto y ambos cumplen el mismo puerto
    assert isinstance(repo, expected)
    assert isinstance(repo, IncidentRepositoryPort)


def test_bdd_s3b_database_url_no_soportada_falla_explicitamente():
    with pytest.raises(ValueError):
        create_repository("mysql://root@localhost/db")


def test_bdd_s4_orquestacion_reproducible_en_dos_contenedores():
    # Given los artefactos de contenedores versionados en la raíz del repositorio
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    # Then la imagen usa python:3.12-slim + uv y arranca la API
    assert "FROM python:3.12-slim" in dockerfile
    assert "uv sync" in dockerfile and "--frozen" in dockerfile
    assert "src.adapters.inbound.api.app:create_app" in dockerfile
    # And .dockerignore excluye entornos y artefactos locales
    for entry in (".venv", ".git", "__pycache__", "*.db"):
        assert entry in dockerignore
    # And compose define db (postgres:16-alpine + volumen + pg_isready) y api dependiente y sana
    assert "postgres:16-alpine" in compose and "pg_isready" in compose
    assert "volumes:" in compose
    assert "DATABASE_URL: postgresql://" in compose and "@db:5432/" in compose
    assert "condition: service_healthy" in compose
    assert "/health" in compose


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Requiere POSTGRES_TEST_URL")
def test_postgres_repository_contra_base_real():
    """Prueba de integración opcional (p. ej. contra el contenedor db de docker compose)."""
    from datetime import datetime

    repo = create_repository(os.environ["POSTGRES_TEST_URL"])
    assert repo.check_health() is True
    service = IncidentService(repo)
    reg = service.create_incident(
        "Prueba PG", "HTTP 502 Bad Gateway en todas las transacciones de la pasarela de pagos",
        incident_id="INC-PGTEST", created_at=datetime(2026, 11, 9, 10, 0),
    )
    assert repo.get_incident("INC-PGTEST").duplicate_group_key == reg.triage.duplicate_group_key
