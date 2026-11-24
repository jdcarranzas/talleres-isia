---
description: "Tareas para 002-active-incidents-summary"
---

# Tasks: Resumen de incidentes activos

**Input**: `/specs/002-active-incidents-summary/` (spec.md, plan.md)

**Tests**: Requeridos por la Constitución (principio III).

## Phase 1: Setup

- [x] T001 Agregar Ruff como dependencia de desarrollo (`uv add --dev ruff`) y `[tool.ruff]`/`[tool.ruff.lint]` en `pyproject.toml`
- [x] T002 [P] Crear `src/domain/ruff.toml`, `src/application/ruff.toml` y `src/adapters/inbound/ruff.toml` con `extend`, TID251 y TID252

## Phase 2: Foundational

- [x] T003 Definir `IncidentRepositoryPort` (`@runtime_checkable Protocol`) en `src/application/ports.py`
- [x] T004 Implementar `SQLiteIncidentRepository` en `src/adapters/outbound/sqlite_repository.py` (esquema, `sla_policies`, índice `(component, status)`, `list_active_incidents` con `INNER JOIN`)
- [x] T005 Implementar `create_repository()` en `src/adapters/outbound/factory.py` (default `sqlite:///:memory:`)

**Checkpoint**: `uv run ruff check src/` en verde.

## Phase 3: User Story 1 — Carga activa e incumplimientos (P1) 🎯 MVP

- [x] T006 [US1] Escribir escenarios 1–3 en `tests/test_spec_002_summary.py` (deben fallar primero)
- [x] T007 [US1] Agregar `get_active_incidents_summary(component_filter, reference_time)` en `src/application/services.py`
- [x] T008 [P] [US1] Agregar `ActiveIncidentItem` y `ActiveIncidentsSummaryResponse` en `src/adapters/inbound/api/schemas.py`
- [x] T009 [US1] Agregar `GET /api/v1/incidents/summary` en `src/adapters/inbound/api/app.py`

## Phase 4: User Story 2 — Paridad CLI (P2)

- [x] T010 [US2] Escribir escenario 4 en `tests/test_spec_002_summary.py`
- [x] T011 [US2] Agregar subcomando `summary` en `src/adapters/inbound/cli.py` usando los mismos schemas

## Phase 5: Polish

- [x] T012 Prueba de conformidad `isinstance(SQLiteIncidentRepository(...), IncidentRepositoryPort)`
- [x] T013 Actualizar `AGENTS.md` y verificar `uv run ruff check src/` + `uv run pytest -v`

## Dependencies

T001–T002 → T003 → T004–T005 → US1 (T006 → T007 → T008/T009) → US2 → Polish.
