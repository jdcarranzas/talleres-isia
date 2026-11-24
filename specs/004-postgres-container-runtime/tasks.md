---
description: "Tareas para 004-postgres-container-runtime"
---

# Tasks: Persistencia PostgreSQL y runtime en contenedores

**Input**: `/specs/004-postgres-container-runtime/` (spec.md, plan.md)

**Prerequisites**: ADR-004 aceptado y `.specify/memory/constitution.md` v1.1.0.

## Phase 1: Setup

- [x] T001 Agregar el driver sin ORM: `uv add "psycopg[binary]"`
- [x] T002 [P] Prohibir `psycopg` en `src/domain/`, `src/application/` y `src/adapters/inbound/` vía `ruff.toml`

## Phase 2: User Story 2 — Selección transparente del motor (P1)

- [x] T003 [US2] Escribir escenario 3 en `tests/test_spec_004_runtime_health.py` (factory + conformidad del puerto)
- [x] T004 [US2] Implementar `PostgresIncidentRepository` en `src/adapters/outbound/postgres_repository.py`
- [x] T005 [US2] Seleccionar PostgreSQL/SQLite en `src/adapters/outbound/factory.py`

## Phase 3: User Story 1 — Chequeo real de salud (P1) 🎯 MVP

- [x] T006 [US1] Escribir escenarios 1–2 (200, CLI, 503 con doble de prueba)
- [x] T007 [US1] Agregar `IncidentService.check_health` en `src/application/services.py`
- [x] T008 [P] [US1] Agregar `HealthResponse` y `GET /health` (200/503) en `src/adapters/inbound/api/`
- [x] T009 [US1] Agregar subcomando `health` en `src/adapters/inbound/cli.py`

## Phase 4: User Story 3 — Orquestación (P2)

- [x] T010 [US3] Escribir escenario 4 (estructura de archivos de contenedores)
- [x] T011 [P] [US3] Crear `Dockerfile` y `.dockerignore`
- [x] T012 [US3] Crear `docker-compose.yml` con `db` y `api`

## Phase 5: Polish

- [x] T013 Prueba opcional contra PostgreSQL real (`POSTGRES_TEST_URL`)
- [x] T014 `uv run ruff check src/`, `uv run pytest -v`, `docker compose config -q`; actualizar `AGENTS.md`

## Dependencies

T001–T002 → US2 → US1 → US3 → Polish.
