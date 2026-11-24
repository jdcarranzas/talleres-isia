"""Adaptador primario REST (FastAPI). Delega toda la lógica en ``IncidentService``.

Ejecución local:  uv run uvicorn --factory src.adapters.inbound.api.app:create_app --port 8000
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    CreateIncidentRequest,
    HealthResponse,
    IncidentCreatedResponse,
    SLAEvaluationResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentNotFoundError, IncidentService, ValidationError


def create_app(service: Optional[IncidentService] = None) -> FastAPI:
    """Construye la aplicación; sin ``service`` explícito usa el repositorio de ``DATABASE_URL``."""
    svc = service or IncidentService(create_repository())
    app = FastAPI(title="IncidentOps API", version="0.2.0")

    @app.exception_handler(ValidationError)
    async def _validation_error(_, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.post("/api/v1/incidents/triage", response_model=TriageResponse)
    def triage(body: TriageRequest) -> TriageResponse:
        return TriageResponse.from_result(svc.triage_incident(body.incident_id, body.raw_text))

    @app.get("/api/v1/incidents/summary", response_model=ActiveIncidentsSummaryResponse)
    def summary(
        component: Optional[str] = Query(default=None),
        reference_time: Optional[datetime] = Query(default=None),
    ) -> ActiveIncidentsSummaryResponse:
        return ActiveIncidentsSummaryResponse.from_summary(
            svc.get_active_incidents_summary(component, reference_time)
        )

    @app.post(
        "/api/v1/incidents",
        response_model=IncidentCreatedResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_incident(body: CreateIncidentRequest) -> IncidentCreatedResponse:
        registration = svc.create_incident(
            title=body.title,
            raw_text=body.raw_text,
            incident_id=body.incident_id,
            created_at=body.created_at,
            status=body.status,
        )
        return IncidentCreatedResponse.from_registration(registration)

    @app.get("/api/v1/incidents/{incident_id}/sla", response_model=SLAEvaluationResponse)
    def incident_sla(
        incident_id: str, reference_time: Optional[datetime] = Query(default=None)
    ) -> SLAEvaluationResponse:
        try:
            evaluation = svc.evaluate_incident_sla(incident_id, reference_time)
        except IncidentNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return SLAEvaluationResponse.from_evaluation(evaluation)

    @app.get("/health", response_model=HealthResponse)
    def health() -> JSONResponse:
        healthy = svc.check_health()
        body = HealthResponse.from_flag(healthy).model_dump()
        code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=code, content=body)

    return app
