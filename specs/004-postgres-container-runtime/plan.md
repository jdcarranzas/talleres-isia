# Implementation Plan: Persistencia PostgreSQL y runtime en contenedores

**Branch**: `004-postgres-container-runtime` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-postgres-container-runtime/spec.md`

## Summary

Implementar `PostgresIncidentRepository` (psycopg 3, sin ORM) que cumple `IncidentRepositoryPort`, seleccionarlo desde `factory.create_repository` por `DATABASE_URL`, exponer `check_health` como caso de uso con `GET /health` y CLI `health`, y empaquetar el servicio en una topología Docker Compose `api` + `db`.

## Technical Context

**Language/Version**: Python ≥ 3.10 (imagen: 3.12-slim)
**Primary Dependencies**: `psycopg[binary]` (nueva, aprobada en ADR-004)
**Storage**: PostgreSQL 16 (producción) / SQLite (desarrollo y pruebas); fechas TEXT ISO 8601 en ambos
**Testing**: pytest; doble de prueba para 503; integración opcional con `POSTGRES_TEST_URL`
**Target Platform**: contenedores Linux (Docker Compose)
**Project Type**: web-service + CLI
**Constraints**: sin ORM; pruebas sin daemon Docker; contenedor sin root
**Scale/Scope**: 1 adaptador, 1 endpoint, 1 subcomando, 3 archivos de contenedores

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | Sin cambios en `src/domain/`. ✅ |
| II. Hexagonal | Nuevo adaptador outbound; inbound solo usa `factory`; Ruff prohíbe `psycopg` fuera de outbound. ✅ |
| III. BDD | 4 escenarios → `tests/test_spec_004_runtime_health.py`. ✅ |
| IV. Persistencia (v1.1.0) | `psycopg[binary]`, SQL parametrizado `%s`, sin ORM, selección por `DATABASE_URL`. ✅ |
| V. Verificación | `ruff check src/` + `pytest -v` sin Docker. ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/004-postgres-container-runtime/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
src/adapters/outbound/postgres_repository.py  # PostgresIncidentRepository: dict_row, %s, ON CONFLICT DO UPDATE,
                                              #   índices, esquema perezoso, check_health() = SELECT 1
src/adapters/outbound/factory.py              # postgresql:// | postgres:// -> Postgres; sqlite:/// | vacío -> SQLite
src/application/services.py                   # check_health() (nunca propaga excepciones)
src/adapters/inbound/api/schemas.py           # HealthResponse
src/adapters/inbound/api/app.py               # GET /health -> 200 | 503
src/adapters/inbound/cli.py                   # health (exit 0 | 1)
Dockerfile                                    # python:3.12-slim + uv sync --frozen --no-dev, usuario no root
.dockerignore
docker-compose.yml                            # db (postgres:16-alpine, volumen, pg_isready) + api (service_healthy, /health)
tests/test_spec_004_runtime_health.py
```

**Structure Decision**: Se agrega un adaptador secundario; sin cambios en dominio ni en la forma del puerto.

## Design Notes

- **Esquema perezoso**: construir el adaptador no abre conexión (permite validar conformidad del puerto sin base); el DDL `IF NOT EXISTS` se ejecuta en el primer uso.
- **Conexión por operación** con `connect_timeout=3`: el chequeo de salud refleja caídas y recuperaciones de la base sin reiniciar la API.
- **Paridad SQLite ↔ PostgreSQL**: mismas columnas, mismos índices, fechas TEXT ISO 8601 con zona.
- **Arranque**: `uvicorn --factory src.adapters.inbound.api.app:create_app` para evitar efectos de import.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| DDL duplicado por dialecto | Paridad sin ORM (ADR-004) | Un ORM está prohibido por la Constitución |
