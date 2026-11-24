"""Selección del adaptador de persistencia a partir de ``DATABASE_URL`` (ADR-004).

- ``postgresql://...`` o ``postgres://...``  -> ``PostgresIncidentRepository``
- ``sqlite:///ruta.db`` / ``sqlite:///:memory:`` o variable ausente -> ``SQLiteIncidentRepository``

Los adaptadores primarios solo importan este módulo; nunca un repositorio concreto.
"""

from __future__ import annotations

import os
from typing import Optional

from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def resolve_database_url(database_url: Optional[str] = None) -> str:
    url = database_url if database_url is not None else os.environ.get("DATABASE_URL", "")
    return url.strip() or DEFAULT_DATABASE_URL


def create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort:
    url = resolve_database_url(database_url)
    if url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        # Importación diferida: SQLite no exige tener psycopg cargado.
        from src.adapters.outbound.postgres_repository import PostgresIncidentRepository

        return PostgresIncidentRepository(url.replace("postgresql+psycopg://", "postgresql://", 1))
    if url.startswith("sqlite:///"):
        from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository

        return SQLiteIncidentRepository(url[len("sqlite:///"):] or ":memory:")
    raise ValueError(
        f"DATABASE_URL no soportada: '{url}'. Use 'sqlite:///...' o 'postgresql://...'."
    )
