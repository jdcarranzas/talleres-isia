"""Fixtures compartidas: cada prueba usa almacenamiento aislado (SQLite en memoria o en tmp_path)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.services import IncidentService
from src.domain.sla_calculator import BUSINESS_TZ

# Reportes de referencia (data/sample_incidents.json)
PAYMENTS_502_OUTAGE = (
    "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones "
    "con tarjeta de crédito desde hace 12 minutos. Ningún comercio puede cobrar."
)
PAYMENTS_502_RECURRENCE = (
    "Otra vez cayó la pasarela de cobros con tarjeta, a nuestros clientes les sale error 502 "
    "al intentar pagar el carrito de compras."
)
LOCKED_ACCOUNT_TODAY = (
    "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. Necesito acceder "
    "hoy mismo porque debo enviar el informe de cierre a la junta directiva."
)
SLOW_DASHBOARD = (
    "El dashboard de reportes históricos tarda cerca de 4.5 segundos en cargar cuando un "
    "cliente tiene más de 10,000 órdenes registradas."
)

FIXED_NOW = datetime(2026, 11, 20, 12, 0, tzinfo=BUSINESS_TZ)


@pytest.fixture
def repository() -> SQLiteIncidentRepository:
    return SQLiteIncidentRepository(":memory:")


@pytest.fixture
def service(repository: SQLiteIncidentRepository) -> IncidentService:
    return IncidentService(repository, clock=lambda: FIXED_NOW)


@pytest.fixture
def client(service: IncidentService) -> TestClient:
    return TestClient(create_app(service))


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_database(tmp_path, monkeypatch) -> str:
    """El CLI crea un repositorio por invocación: se comparte un archivo SQLite aislado."""
    url = f"sqlite:///{tmp_path / 'incidentops-test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url
