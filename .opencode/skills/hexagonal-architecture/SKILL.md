---
name: hexagonal-architecture
description: Reglas de capas de IncidentOps (dominio, aplicación, adaptadores inbound/outbound) y su verificación con Ruff. Úsala antes de crear, mover o revisar código en src/, al añadir un endpoint, comando CLI o adaptador de base de datos, o cuando `uv run ruff check src/` reporte TID251/TID252.
---

# Arquitectura Hexagonal en IncidentOps

Fuente de verdad: `docs/adr/003-arquitectura-hexagonal.md` y `.specify/memory/constitution.md`.

## Qué puede importar cada capa

| Capa | Puede importar | Nunca importa |
| :--- | :--- | :--- |
| `src/domain/` | stdlib, `src.domain` | fastapi, starlette, pydantic, typer, uvicorn, sqlite3, psycopg, ORMs, `src.application`, `src.adapters` |
| `src/application/` | stdlib, `src.domain` | frameworks HTTP/CLI, pydantic, drivers BD, ORMs, `src.adapters` |
| `src/adapters/inbound/` | fastapi, pydantic, typer, `src.application`, tipos de `src.domain.models`, `src.adapters.outbound.factory` | sqlite3, psycopg, repositorios concretos, `triage_rules`/`sla_calculator` directamente |
| `src/adapters/outbound/` | drivers BD, `src.domain`, `src.application.ports` | adaptadores inbound |

## Reglas de trabajo

1. **Lógica de negocio solo en `src/domain/`.** Si un adaptador necesita una regla (severidad, SLA, clave de duplicados), invoca `IncidentService`; no la reescribe.
2. **Un caso de uso por capacidad en `IncidentService`** (`src/application/services.py`). Errores de negocio como excepciones propias (`ValidationError` → 422 / exit 1, `IncidentNotFoundError` → 404 / exit 1).
3. **Paridad REST ↔ CLI obligatoria**: toda capacidad nueva se expone en `src/adapters/inbound/api/app.py` **y** en `src/adapters/inbound/cli.py`, ambos llamando al mismo método de `IncidentService` y serializando con los mismos modelos de `api/schemas.py`.
4. **Persistencia**: nuevos métodos se declaran primero en `IncidentRepositoryPort` (`src/application/ports.py`, `typing.Protocol` `@runtime_checkable`) y luego se implementan en **todos** los adaptadores de `src/adapters/outbound/`. Los adaptadores inbound obtienen el repositorio solo con `create_repository()` de `factory.py`.
5. Imports absolutos (`from src.domain.models import ...`); nada de `from ..`.

## Verificación estática

- `pyproject.toml`: `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]` y `ban-relative-imports = "parents"`.
- `ruff.toml` jerárquicos con `extend` al `pyproject.toml` y `[lint.flake8-tidy-imports.banned-api]` en `src/domain/`, `src/application/` y `src/adapters/inbound/`.
- Ejecuta `uv run ruff check src/` tras cada cambio; debe terminar en `All checks passed!`. Un `TID251` significa que el código salta una frontera: corrige el diseño, no la regla.
- Si una frontera debe cambiar, primero se escribe un ADR (skill `adr-writer`).
