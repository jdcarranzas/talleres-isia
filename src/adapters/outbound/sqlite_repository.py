"""Adaptador secundario SQLite (biblioteca estándar ``sqlite3``) de ``IncidentRepositoryPort``.

Extrae la persistencia optimizada de la Semana 1: el filtrado ocurre en SQL con
``INNER JOIN sla_policies`` sobre el índice compuesto ``(component, status)`` (sin escaneo
completo en memoria ni consultas N+1). Las marcas temporales se guardan como TEXT ISO 8601.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Sequence

from src.domain.models import ACTIVE_STATUSES, OPEN_STATUSES, Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE

_COLUMNS = (
    "incident_id, title, component, severity, status, created_at, resolved_at, "
    "recommended_team, duplicate_group_key"
)

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS sla_policies (
        severity TEXT PRIMARY KEY,
        max_resolution_minutes INTEGER NOT NULL,
        operates_24x7 INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        component TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        recommended_team TEXT,
        duplicate_group_key TEXT
    )
    """,
)

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status)",
)


def _placeholders(values: Sequence[str]) -> str:
    return ", ".join("?" for _ in values)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _row_to_incident(row: sqlite3.Row) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        component=row["component"],
        severity=row["severity"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolved_at=_parse_dt(row["resolved_at"]),
        recommended_team=row["recommended_team"],
        duplicate_group_key=row["duplicate_group_key"],
    )


class SQLiteIncidentRepository:
    """Implementación de ``IncidentRepositoryPort`` sobre ``sqlite3`` estándar."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        # check_same_thread=False + lock: FastAPI/TestClient atienden en hilos distintos.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            for ddl in _SCHEMA:
                self._conn.execute(ddl)
            # Migración aditiva para bases creadas antes del Hito 003.
            existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(incidents)")}
            for column in ("recommended_team", "duplicate_group_key"):
                if column not in existing:
                    self._conn.execute(f"ALTER TABLE incidents ADD COLUMN {column} TEXT")
            for ddl in _INDEXES:
                self._conn.execute(ddl)
            self._conn.executemany(
                "INSERT OR REPLACE INTO sla_policies (severity, max_resolution_minutes, operates_24x7) "
                "VALUES (?, ?, ?)",
                [
                    (r.severity, r.max_resolution_minutes, 1 if r.operates_24x7 else 0)
                    for r in SLA_POLICY_TABLE.values()
                ],
            )

    # --- IncidentRepositoryPort -------------------------------------------------
    def save_incident(self, incident: Incident) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO incidents ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
        return _row_to_incident(row) if row else None

    def find_open_duplicates(
        self, duplicate_group_key: str, exclude_incident_id: Optional[str] = None
    ) -> List[Incident]:
        query = (
            f"SELECT {_COLUMNS} FROM incidents "
            f"WHERE duplicate_group_key = ? AND status IN ({_placeholders(OPEN_STATUSES)})"
        )
        params: List[str] = [duplicate_group_key, *OPEN_STATUSES]
        if exclude_incident_id:
            query += " AND incident_id <> ?"
            params.append(exclude_incident_id)
        query += " ORDER BY created_at, incident_id"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [_row_to_incident(r) for r in rows]

    def list_active_incidents(self, component: Optional[str] = None) -> List[Incident]:
        columns = ", ".join(f"i.{c.strip()}" for c in _COLUMNS.split(","))
        query = (
            f"SELECT {columns} FROM incidents i "
            "INNER JOIN sla_policies p ON p.severity = i.severity "
            f"WHERE i.status IN ({_placeholders(ACTIVE_STATUSES)})"
        )
        params: List[str] = [*ACTIVE_STATUSES]
        if component:
            query += " AND i.component = ?"
            params.append(component)
        query += " ORDER BY i.created_at, i.incident_id"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [_row_to_incident(r) for r in rows]

    def check_health(self) -> bool:
        try:
            with self._lock:
                return self._conn.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False
