"""Casos de uso compartidos de IncidentOps.

``IncidentService`` es el único punto de entrada al núcleo para todos los adaptadores
primarios (REST, CLI y, a futuro, MCP). Solo depende de ``src.domain`` y del puerto
``IncidentRepositoryPort``; nunca de FastAPI, Typer ni de un driver de base de datos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from src.application.ports import IncidentRepositoryPort
from src.domain.models import VALID_STATUSES, Incident, SLAEvaluation, TriageResult
from src.domain.sla_calculator import BUSINESS_TZ, evaluate_sla_status, normalize_timestamp
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Entrada inválida para un caso de uso (API -> 422, CLI -> código de salida 1)."""


class IncidentNotFoundError(LookupError):
    """El incidente solicitado no existe (API -> 404, CLI -> código de salida 1)."""


@dataclass(frozen=True)
class ActiveIncidentItem:
    incident_id: str
    title: str
    component: str
    severity: str
    status: str
    elapsed_minutes: int
    is_breached: bool
    requires_escalation: bool


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    reference_time: datetime
    component_filter: Optional[str]
    total_active: int
    breached_count: int
    incidents: Tuple[ActiveIncidentItem, ...]


@dataclass(frozen=True)
class IncidentRegistration:
    incident: Incident
    triage: TriageResult
    is_duplicate: bool
    duplicate_of: Tuple[str, ...]


def _now() -> datetime:
    return datetime.now(BUSINESS_TZ)


def _require_text(value: Optional[str], field: str) -> str:
    if value is None or not value.strip():
        raise ValidationError(f"El campo '{field}' es obligatorio y no puede estar vacío.")
    return value.strip()


class IncidentService:
    """Casos de uso de triaje, resumen, ciclo de vida, SLA y salud operativa."""

    def __init__(
        self,
        repository: Optional[IncidentRepositoryPort] = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    @property
    def repository(self) -> IncidentRepositoryPort:
        if self._repository is None:
            raise RuntimeError("Este caso de uso requiere un IncidentRepositoryPort configurado.")
        return self._repository

    # --- Hito 001 --------------------------------------------------------------
    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Clasifica un reporte sin persistirlo (operación stateless)."""
        return classify_incident_report(
            _require_text(incident_id, "incident_id"), _require_text(raw_text, "raw_text")
        )

    # --- Hito 002 --------------------------------------------------------------
    def get_active_incidents_summary(
        self,
        component_filter: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ActiveIncidentsSummary:
        """Resumen de incidentes OPEN/IN_PROGRESS con su estado de SLA a ``reference_time``."""
        component = component_filter.strip() if component_filter and component_filter.strip() else None
        reference = normalize_timestamp(reference_time) if reference_time else self._clock()

        items: List[ActiveIncidentItem] = []
        for incident in self.repository.list_active_incidents(component):
            created_at = normalize_timestamp(incident.created_at)
            # Un incidente registrado "en el futuro" respecto a la referencia aún no consume SLA.
            evaluation = evaluate_sla_status(incident, max(reference, created_at))
            items.append(
                ActiveIncidentItem(
                    incident_id=incident.incident_id,
                    title=incident.title,
                    component=incident.component,
                    severity=incident.severity,
                    status=incident.status,
                    elapsed_minutes=evaluation.elapsed_minutes,
                    is_breached=evaluation.is_breached,
                    requires_escalation=evaluation.requires_escalation,
                )
            )
        return ActiveIncidentsSummary(
            reference_time=reference,
            component_filter=component,
            total_active=len(items),
            breached_count=sum(1 for item in items if item.is_breached),
            incidents=tuple(items),
        )

    # --- Hito 003 --------------------------------------------------------------
    def create_incident(
        self,
        title: str,
        raw_text: str,
        incident_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        status: str = "OPEN",
    ) -> IncidentRegistration:
        """Clasifica, detecta duplicados abiertos y persiste un incidente entrante."""
        clean_title = _require_text(title, "title")
        clean_text = _require_text(raw_text, "raw_text")
        if incident_id is not None and not incident_id.strip():
            raise ValidationError("El campo 'incident_id' no puede estar vacío si se envía.")
        new_id = incident_id.strip() if incident_id else f"INC-{uuid.uuid4().hex[:8].upper()}"
        if status not in VALID_STATUSES:
            raise ValidationError(f"Estado no válido: {status}. Válidos: {sorted(VALID_STATUSES)}")

        triage = classify_incident_report(new_id, clean_text)
        moment = normalize_timestamp(created_at) if created_at else self._clock()
        incident = Incident(
            incident_id=new_id,
            title=clean_title,
            component=triage.component,
            severity=triage.severity,
            status=status,  # type: ignore[arg-type]
            created_at=moment,
            resolved_at=moment if status == "RESOLVED" else None,
            recommended_team=triage.recommended_team,
            duplicate_group_key=triage.duplicate_group_key,
        )
        duplicates = self.repository.find_open_duplicates(
            triage.duplicate_group_key, exclude_incident_id=new_id
        )
        self.repository.save_incident(incident)
        duplicate_ids = tuple(d.incident_id for d in duplicates)
        return IncidentRegistration(
            incident=incident,
            triage=triage,
            is_duplicate=bool(duplicate_ids),
            duplicate_of=duplicate_ids,
        )

    def evaluate_incident_sla(
        self, incident_id: str, reference_time: Optional[datetime] = None
    ) -> SLAEvaluation:
        """Audita el SLA de un incidente registrado en un instante de referencia."""
        incident = self.repository.get_incident(_require_text(incident_id, "incident_id"))
        if incident is None:
            raise IncidentNotFoundError(f"No existe el incidente '{incident_id}'.")
        reference = normalize_timestamp(reference_time) if reference_time else self._clock()
        if incident.resolved_at is None and reference < normalize_timestamp(incident.created_at):
            raise ValidationError("reference_time no puede ser anterior a created_at del incidente.")
        try:
            return evaluate_sla_status(incident, reference)
        except ValueError as exc:  # severidad inválida o fin anterior a creación
            raise ValidationError(str(exc)) from exc

    # --- Hito 004 --------------------------------------------------------------
    def check_health(self) -> bool:
        """``True`` si la persistencia configurada responde; nunca propaga excepciones."""
        try:
            return bool(self.repository.check_health())
        except Exception:
            return False
