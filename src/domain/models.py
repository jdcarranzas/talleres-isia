"""Entidades de dominio y tipos de datos para IncidentOps."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, FrozenSet, Literal, Optional, Tuple

SeverityLevel = Literal["P0", "P1", "P2", "P3"]
IncidentStatus = Literal["OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"]
TeamName = Literal["Backend-Core", "Platform-SRE", "Data-DBA", "Security-IAM"]

ImpactScope = Literal["global", "shared", "individual", "non_production"]
"""Radio de afectación del incidente; junto al síntoma determina la severidad."""

SymptomCategory = Literal[
    "tenant_leak",       # brecha de aislamiento multi-tenant / fuga de datos
    "http_5xx",          # errores 5xx / indisponibilidad
    "connection_pool",   # saturación de conexiones en infraestructura compartida
    "cert_expiry",       # vencimiento de certificados
    "auth",              # bloqueo de cuenta / credenciales
    "export_latency",    # lentitud en exportaciones (batch)
    "latency",           # lentitud en consultas / dashboards
    "ui",                # cambios cosméticos
    "other",             # sin señales reconocidas -> revisión humana
]

SEVERITY_RANK: Dict[SeverityLevel, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

VALID_STATUSES: FrozenSet[str] = frozenset({"OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"})
VALID_TEAMS: FrozenSet[str] = frozenset({"Backend-Core", "Platform-SRE", "Data-DBA", "Security-IAM"})

ACTIVE_STATUSES: Tuple[IncidentStatus, ...] = ("OPEN", "IN_PROGRESS")
"""Estados que cuentan como 'en curso' en el resumen operativo (Hito 002)."""

OPEN_STATUSES: Tuple[IncidentStatus, ...] = ("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")
"""Estados 'abiertos' para la detección de duplicados (Hito 003): todo lo que no está RESOLVED."""


@dataclass(frozen=True)
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75


@dataclass
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    recommended_team: Optional[TeamName] = None
    duplicate_group_key: Optional[str] = None


@dataclass(frozen=True)
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool


@dataclass
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: TeamName
    symptom_category: SymptomCategory
    impact_scope: ImpactScope
    rationale: str
    consistency_ratio: float = 1.0
    symptom_signature: Optional[str] = None
    """Firma estable y más específica del síntoma (p. ej. ``http-502-outage``)."""

    @property
    def duplicate_group_key(self) -> str:
        """Clave normalizada ``<component>:<firma>`` para detectar recurrencias.

        Usa la firma específica del síntoma si existe; si no, la categoría.
        """
        return f"{self.component}:{self.symptom_signature or self.symptom_category}"

    def to_output_line(self) -> str:
        """Serializa el resultado en el formato <output> acordado."""
        return (
            f"severity={self.severity} | component={self.component} | "
            f"recommended_team={self.recommended_team} | "
            f"symptom_category={self.symptom_category} | "
            f"duplicate_group_key={self.duplicate_group_key}"
        )

@dataclass(frozen=True)
class DuplicateGroup:
    """Incidentes que comparten la misma duplicate_group_key."""

    duplicate_group_key: str
    incident_ids: Tuple[str, ...]
    highest_severity: SeverityLevel
    recommended_team: TeamName

    @property
    def occurrences(self) -> int:
        return len(self.incident_ids)

    @property
    def is_recurrent(self) -> bool:
        return self.occurrences > 1
