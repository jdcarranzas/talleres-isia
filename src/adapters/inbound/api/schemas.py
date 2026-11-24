"""Contratos Pydantic v2 compartidos por los adaptadores primarios (REST y CLI).

El CLI serializa con estos mismos modelos para garantizar paridad exacta de campos.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field

from src.application.services import ActiveIncidentsSummary, IncidentRegistration
from src.domain.models import SLAEvaluation, TriageResult


def _not_blank(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("no puede estar vacío ni contener solo espacios")
    return value.strip()


NonBlankStr = Annotated[str, AfterValidator(_not_blank)]
"""Texto obligatorio: vacío o solo espacios -> 422 Unprocessable Entity."""


# --- Hito 001 ---------------------------------------------------------------------
class TriageRequest(BaseModel):
    incident_id: NonBlankStr
    raw_text: NonBlankStr


class TriageResponse(BaseModel):
    incident_id: str
    severity: str
    component: str
    recommended_team: str
    symptom_category: str
    impact_scope: str
    rationale: str
    consistency_ratio: float
    duplicate_group_key: str

    @classmethod
    def from_result(cls, result: TriageResult) -> "TriageResponse":
        return cls(
            incident_id=result.incident_id,
            severity=result.severity,
            component=result.component,
            recommended_team=result.recommended_team,
            symptom_category=result.symptom_category,
            impact_scope=result.impact_scope,
            rationale=result.rationale,
            consistency_ratio=result.consistency_ratio,
            duplicate_group_key=result.duplicate_group_key,
        )


# --- Hito 002 ---------------------------------------------------------------------
class ActiveIncidentItem(BaseModel):
    incident_id: str
    title: str
    component: str
    severity: str
    status: str
    elapsed_minutes: int
    is_breached: bool
    requires_escalation: bool


class ActiveIncidentsSummaryResponse(BaseModel):
    reference_time: datetime
    component: Optional[str]
    total_active: int
    breached_count: int
    incidents: List[ActiveIncidentItem]

    @classmethod
    def from_summary(cls, summary: ActiveIncidentsSummary) -> "ActiveIncidentsSummaryResponse":
        return cls(
            reference_time=summary.reference_time,
            component=summary.component_filter,
            total_active=summary.total_active,
            breached_count=summary.breached_count,
            incidents=[ActiveIncidentItem(**vars(item)) for item in summary.incidents],
        )


# --- Hito 003 ---------------------------------------------------------------------
class CreateIncidentRequest(BaseModel):
    title: NonBlankStr
    raw_text: NonBlankStr
    incident_id: Optional[NonBlankStr] = None
    created_at: Optional[datetime] = None
    status: Literal["OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"] = "OPEN"


class IncidentCreatedResponse(TriageResponse):
    title: str
    status: str
    created_at: datetime
    is_duplicate: bool
    duplicate_of: List[str] = Field(default_factory=list)

    @classmethod
    def from_registration(cls, reg: IncidentRegistration) -> "IncidentCreatedResponse":
        base = TriageResponse.from_result(reg.triage).model_dump()
        return cls(
            **base,
            title=reg.incident.title,
            status=reg.incident.status,
            created_at=reg.incident.created_at,
            is_duplicate=reg.is_duplicate,
            duplicate_of=list(reg.duplicate_of),
        )


class SLAEvaluationResponse(BaseModel):
    incident_id: str
    severity: str
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

    @classmethod
    def from_evaluation(cls, evaluation: SLAEvaluation) -> "SLAEvaluationResponse":
        return cls(**vars(evaluation))


# --- Hito 004 ---------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["connected", "unavailable"]

    @classmethod
    def from_flag(cls, healthy: bool) -> "HealthResponse":
        return cls(status="ok", database="connected") if healthy else cls(
            status="error", database="unavailable"
        )
