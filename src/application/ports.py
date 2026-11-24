"""Puertos secundarios (driven ports) del núcleo de IncidentOps.

Los adaptadores en ``src/adapters/outbound/`` implementan estos contratos; la capa de
aplicación solo conoce el ``Protocol`` y nunca un motor de base de datos concreto.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from src.domain.models import Incident


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Contrato de persistencia de incidentes (SQLite, PostgreSQL o dobles de prueba)."""

    def save_incident(self, incident: Incident) -> None:
        """Inserta el incidente o lo reemplaza si ya existe el mismo ``incident_id``."""
        ...

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Devuelve el incidente o ``None`` si no existe."""
        ...

    def find_open_duplicates(
        self, duplicate_group_key: str, exclude_incident_id: Optional[str] = None
    ) -> List[Incident]:
        """Incidentes abiertos (``OPEN_STATUSES``) con la misma clave, ordenados por creación."""
        ...

    def list_active_incidents(self, component: Optional[str] = None) -> List[Incident]:
        """Incidentes activos (``ACTIVE_STATUSES``), opcionalmente filtrados por componente."""
        ...

    def check_health(self) -> bool:
        """``True`` si el motor responde a una consulta real (``SELECT 1``)."""
        ...
