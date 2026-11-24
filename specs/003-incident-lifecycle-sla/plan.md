# Implementation Plan: Ciclo de vida, duplicados y auditoría de SLA

**Branch**: `003-incident-lifecycle-sla` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-incident-lifecycle-sla/spec.md`

## Summary

Añadir dos casos de uso a `IncidentService` (`create_incident`, `evaluate_incident_sla`) apoyados en los métodos ya declarados del puerto (`save_incident`, `get_incident`, `find_open_duplicates`), extender la entidad `Incident` y exponer ambos casos por REST y CLI con contratos compartidos.

## Technical Context

**Language/Version**: Python ≥ 3.10 (uv)
**Primary Dependencies**: FastAPI, Pydantic v2, Typer (sin nuevas)
**Storage**: SQLite (`sqlite3`), fechas TEXT ISO 8601
**Testing**: pytest + `TestClient` + `CliRunner` (DB SQLite en `tmp_path` para CLI)
**Target Platform**: Linux/Windows/macOS
**Project Type**: web-service + CLI
**Performance Goals**: detección de duplicados por índice `(duplicate_group_key, status)`
**Constraints**: determinismo (reloj inyectable en `IncidentService`); sin ORM
**Scale/Scope**: 2 endpoints, 2 subcomandos, 2 casos de uso

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | Clasificación y SLA solo vía `triage_rules`/`sla_calculator`; estados abiertos definidos en `domain/models.py`. ✅ |
| II. Hexagonal | Casos de uso en `application`; adaptadores solo traducen HTTP/CLI ↔ servicio. ✅ |
| III. BDD | 5 escenarios → `tests/test_spec_003_lifecycle_sla.py`. ✅ |
| IV. Persistencia | Columnas nuevas aditivas en SQLite; SQL parametrizado. ✅ |
| V. Verificación | Ruff sin nuevas excepciones. ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/003-incident-lifecycle-sla/
├── spec.md
├── plan.md   # research/data-model/contratos condensados (anti-verbosidad)
└── tasks.md
```

### Source Code (repository root)

```text
src/domain/models.py            # Incident + recommended_team: Optional[TeamName] = None,
                                #   duplicate_group_key: Optional[str] = None; OPEN_STATUSES / ACTIVE_STATUSES
src/domain/sla_calculator.py    # normalize_timestamp(): naive -> America/Bogota, aware -> convertido
src/application/services.py     # create_incident, evaluate_incident_sla, IncidentNotFoundError
src/adapters/outbound/sqlite_repository.py  # columnas nuevas + ALTER aditivo, idx_incidents_dup_key
                                            #   (duplicate_group_key, status); save/get/find_open_duplicates
src/adapters/inbound/api/schemas.py  # CreateIncidentRequest, IncidentCreatedResponse, SLAEvaluationResponse
src/adapters/inbound/api/app.py      # POST /api/v1/incidents (201), GET /api/v1/incidents/{incident_id}/sla
src/adapters/inbound/cli.py          # create, sla
tests/test_spec_003_lifecycle_sla.py
```

**Structure Decision**: Sin cambios de estructura; se extienden capas existentes.

## Design Notes

- **Orden en `create_incident`**: clasificar → buscar duplicados abiertos excluyendo el propio ID → guardar (upsert). Así un reenvío del mismo ID no se marca como duplicado de sí mismo.
- **Errores**: `ValidationError` → 422 (handler global FastAPI) / exit 1; `IncidentNotFoundError` → 404 / exit 1.
- **Normalización temporal**: todas las fechas se guardan *aware* (`-05:00`) en ISO 8601, evitando `TypeError` al comparar naive vs aware.
- **ID autogenerado**: `INC-` + 8 hex en mayúsculas de `uuid4`.

## Complexity Tracking

Sin violaciones.
