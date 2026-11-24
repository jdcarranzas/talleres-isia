"""Adaptador secundario PostgreSQL (``psycopg`` 3, sin ORM) de ``IncidentRepositoryPort``.

Decisión registrada en ADR-004: SQL parametrizado (``%s``), ``dict_row``,
``INSERT ... ON CONFLICT DO UPDATE`` y marcas temporales en TEXT ISO 8601 para mantener
paridad temporal exacta con el adaptador SQLite. El esquema se crea de forma perezosa en
el primer uso, de modo que construir el adaptador no exige una base disponible.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import psycopg
from psycopg.rows import dict_row

from src.domain.models import ACTIVE_STATUSES, OPEN_STATUSES, Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE

_COLUMNS = (
    "incident_id, title, component, severity, status, created_at, resolved_at, "
    "recommended_team, duplicate_group_key"
)

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS sla_policies (
        severity TEXT PRIMARY KEY,
        max_resolution_minutes INTEGER NOT NULL,
        operates_24x7 BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        component TEXT NOT NULL,
        severity TEXT NOT NULL REFERENCES sla_policies (severity),
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        recommended_team TEXT,
        duplicate_group_key TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status)",
)


def _placeholders(values: Sequence[str]) -> str:
    return ", ".join("%s" for _ in values)


def _row_to_incident(row: Dict[str, Any]) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        component=row["component"],
        severity=row["severity"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        recommended_team=row["recommended_team"],
        duplicate_group_key=row["duplicate_group_key"],
    )


class PostgresIncidentRepository:
    """Implementación de ``IncidentRepositoryPort`` sobre PostgreSQL con ``psycopg``."""

    def __init__(self, database_url: str, connect_timeout: int = 3) -> None:
        self.database_url = database_url
        self._connect_timeout = connect_timeout
        self._schema_ready = False
        self._lock = threading.Lock()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(
            self.database_url, row_factory=dict_row, connect_timeout=self._connect_timeout
        )

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._lock:
            if self._schema_ready:
                return
            with self._connect() as conn:
                for ddl in _DDL:
                    conn.execute(ddl)
                for rule in SLA_POLICY_TABLE.values():
                    conn.execute(
                        "INSERT INTO sla_policies (severity, max_resolution_minutes, operates_24x7) "
                        "VALUES (%s, %s, %s) ON CONFLICT (severity) DO UPDATE SET "
                        "max_resolution_minutes = EXCLUDED.max_resolution_minutes, "
                        "operates_24x7 = EXCLUDED.operates_24x7",
                        (rule.severity, rule.max_resolution_minutes, rule.operates_24x7),
                    )
            self._schema_ready = True

    def _fetch_all(self, query: str, params: Sequence[Any]) -> List[Incident]:
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_incident(r) for r in rows]

    # --- IncidentRepositoryPort -------------------------------------------------
    def save_incident(self, incident: Incident) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO incidents ({_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id) DO UPDATE SET "
                "title = EXCLUDED.title, component = EXCLUDED.component, "
                "severity = EXCLUDED.severity, status = EXCLUDED.status, "
                "created_at = EXCLUDED.created_at, resolved_at = EXCLUDED.resolved_at, "
                "recommended_team = EXCLUDED.recommended_team, "
                "duplicate_group_key = EXCLUDED.duplicate_group_key",
                (
                    incident.incident_id,
                    incident.title,
                    incident.component,
                    incident.severity,
                    incident.status,
                    incident.created_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                    incident.recommended_team,
                    incident.duplicate_group_key,
                ),
            )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        found = self._fetch_all(
            f"SELECT {_COLUMNS} FROM incidents WHERE incident_id = %s", (incident_id,)
        )
        return found[0] if found else None

    def find_open_duplicates(
        self, duplicate_group_key: str, exclude_incident_id: Optional[str] = None
    ) -> List[Incident]:
        query = (
            f"SELECT {_COLUMNS} FROM incidents "
            f"WHERE duplicate_group_key = %s AND status IN ({_placeholders(OPEN_STATUSES)})"
        )
        params: List[Any] = [duplicate_group_key, *OPEN_STATUSES]
        if exclude_incident_id:
            query += " AND incident_id <> %s"
            params.append(exclude_incident_id)
        return self._fetch_all(query + " ORDER BY created_at, incident_id", params)

    def list_active_incidents(self, component: Optional[str] = None) -> List[Incident]:
        columns = ", ".join(f"i.{c.strip()}" for c in _COLUMNS.split(","))
        query = (
            f"SELECT {columns} FROM incidents i "
            "INNER JOIN sla_policies p ON p.severity = i.severity "
            f"WHERE i.status IN ({_placeholders(ACTIVE_STATUSES)})"
        )
        params: List[Any] = [*ACTIVE_STATUSES]
        if component:
            query += " AND i.component = %s"
            params.append(component)
        return self._fetch_all(query + " ORDER BY i.created_at, i.incident_id", params)

    def check_health(self) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT 1 AS ok").fetchone()
            return bool(row) and row["ok"] == 1
        except psycopg.Error:
            return False
