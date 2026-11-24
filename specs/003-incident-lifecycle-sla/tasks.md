---
description: "Tareas para 003-incident-lifecycle-sla"
---

# Tasks: Ciclo de vida, duplicados y auditoría de SLA

**Input**: `/specs/003-incident-lifecycle-sla/` (spec.md, plan.md)

**Tests**: Requeridos por la Constitución (principio III).

## Phase 1: Foundational (dominio y persistencia)

- [x] T001 Extender `Incident` con `recommended_team` y `duplicate_group_key`; agregar `OPEN_STATUSES`/`ACTIVE_STATUSES`/`VALID_STATUSES` en `src/domain/models.py`
- [x] T002 [P] Agregar `normalize_timestamp` y usarlo en `evaluate_sla_status` en `src/domain/sla_calculator.py`
- [x] T003 Agregar columnas, migración aditiva e índice `idx_incidents_dup_key` en `src/adapters/outbound/sqlite_repository.py`; completar `save_incident`, `get_incident`, `find_open_duplicates`

**Checkpoint**: `uv run pytest -v` de 001/002 sigue en verde.

## Phase 2: User Story 1 — Registro y duplicados (P1) 🎯 MVP

- [x] T004 [US1] Escribir escenarios 1–2 en `tests/test_spec_003_lifecycle_sla.py`
- [x] T005 [US1] Implementar `IncidentService.create_incident` en `src/application/services.py`
- [x] T006 [P] [US1] Agregar `CreateIncidentRequest` e `IncidentCreatedResponse` en `src/adapters/inbound/api/schemas.py`
- [x] T007 [US1] Agregar `POST /api/v1/incidents` (201) en `src/adapters/inbound/api/app.py`

## Phase 3: User Story 2 — Auditoría de SLA (P1)

- [x] T008 [US2] Escribir escenarios 3–4 en `tests/test_spec_003_lifecycle_sla.py`
- [x] T009 [US2] Implementar `evaluate_incident_sla` + `IncidentNotFoundError` en `src/application/services.py`
- [x] T010 [P] [US2] Agregar `SLAEvaluationResponse` y `GET /api/v1/incidents/{incident_id}/sla` (404/422)

## Phase 4: User Story 3 — CLI (P2)

- [x] T011 [US3] Escribir escenario 5 (CLI) en `tests/test_spec_003_lifecycle_sla.py`
- [x] T012 [US3] Agregar subcomandos `create` y `sla` en `src/adapters/inbound/cli.py`

## Phase 5: Polish

- [x] T013 `uv run ruff check src/` + `uv run pytest -v` al 100 %

## Dependencies

T001–T003 → US1 → US2 → US3 → Polish.
