# Implementation Plan: Resumen de incidentes activos

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-active-incidents-summary/spec.md`

## Summary

Exponer el resumen de incidentes activos por REST y CLI reutilizando un único caso de uso `IncidentService.get_active_incidents_summary`, que consulta un nuevo puerto `IncidentRepositoryPort` y calcula el SLA con el dominio. Se introduce la persistencia SQLite optimizada (JOIN + índice compuesto) como primer adaptador secundario y se automatiza la verificación de fronteras con Ruff.

## Technical Context

**Language/Version**: Python ≥ 3.10 (uv)
**Primary Dependencies**: FastAPI, Pydantic v2, Typer (ya instaladas en H001); Ruff (dev)
**Storage**: SQLite (`sqlite3` estándar), `DATABASE_URL` por defecto `sqlite:///:memory:`
**Testing**: pytest + `TestClient` + `CliRunner`
**Target Platform**: Linux/Windows/macOS
**Project Type**: web-service + CLI
**Performance Goals**: filtrado en SQL (sin escaneo completo ni N+1) sobre ~10k filas
**Constraints**: determinismo (`reference_time` inyectable); sin ORM
**Scale/Scope**: 1 endpoint, 1 subcomando, 1 puerto, 1 adaptador

## Constitution Check

| Principio | Cumplimiento |
| :--- | :--- |
| I. Dominio único | El SLA se calcula con `src/domain/sla_calculator.py`; el adaptador no reimplementa reglas. ✅ |
| II. Hexagonal | Puerto `Protocol` en `application/ports.py`; inbound usa `factory.py`. ✅ |
| III. BDD | 4 escenarios → `tests/test_spec_002_summary.py`. ✅ |
| IV. Persistencia sin ORM | `sqlite3` + SQL parametrizado. ✅ |
| V. Verificación | Ruff `E4,E7,E9,F,TID` + `ruff.toml` jerárquicos. ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── spec.md
├── plan.md      # research, data-model y contratos condensados aquí (curaduría anti-verbosidad)
└── tasks.md
```

### Source Code (repository root)

```text
src/application/ports.py                    # IncidentRepositoryPort: save_incident, get_incident,
                                            #   find_open_duplicates, list_active_incidents, check_health
src/application/services.py                 # + get_active_incidents_summary(component_filter, reference_time)
src/adapters/outbound/sqlite_repository.py  # SQLiteIncidentRepository (INNER JOIN sla_policies,
                                            #   idx_incidents_component_status (component, status))
src/adapters/outbound/factory.py            # create_repository(DATABASE_URL)
src/adapters/inbound/api/schemas.py         # ActiveIncidentItem, ActiveIncidentsSummaryResponse
src/adapters/inbound/api/app.py             # GET /api/v1/incidents/summary?component=&reference_time=
src/adapters/inbound/cli.py                 # summary [--component] [--reference-time]
pyproject.toml                              # [tool.ruff.lint] select = ["E4","E7","E9","F","TID"]
src/{domain,application,adapters/inbound}/ruff.toml  # extend + TID251 banned-api + TID252 parents
tests/test_spec_002_summary.py              # 4 escenarios + conformidad del puerto
```

**Structure Decision**: Proyecto único con capas hexagonales de ADR-003.

## Design Notes (research + data model + contracts)

- **Puerto completo desde ahora**: se declaran los 5 métodos del roadmap (H002–H004) para que el contrato del repositorio no cambie en cada hito; los no usados en H002 se implementan en SQLite igualmente.
- **Contrato** `ActiveIncidentsSummaryResponse`: `{reference_time, component, total_active, breached_count, incidents: [ActiveIncidentItem]}`; `ActiveIncidentItem`: `{incident_id, title, component, severity, status, elapsed_minutes, is_breached, requires_escalation}`.
- **Fechas**: `reference_time` naive se interpreta en hora de negocio (America/Bogota), igual que el dominio.
- El repositorio heredado `src/incident_repository.py` queda como benchmark de referencia; no se usa desde los adaptadores.

## Complexity Tracking

Sin violaciones.
