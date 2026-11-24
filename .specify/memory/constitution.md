<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: principio IV ampliado por ADR-004)
- Modified principles: IV. Persistencia sin ORM detrás de puertos (antes: "SQLite3 estándar únicamente")
- Added sections: none
- Removed sections: none
- Templates requiring updates: ✅ .specify/templates/plan-template.md (Constitution Check usa estos principios, sin cambios de estructura)
  ✅ .specify/templates/spec-template.md (sin cambios) ✅ .specify/templates/tasks-template.md (sin cambios)
- Follow-up TODOs: none
- History: 1.0.0 (2026-11-23) formalizada desde docs/constitution.md + ADR-003 con /speckit.constitution;
  1.1.0 (2026-11-23) incorpora ADR-004 antes de especificar la Feature 004.
-->

# IncidentOps Constitution

## Core Principles

### I. Núcleo de dominio determinista y único

Las reglas de negocio viven solo en `src/domain/` (`models.py`, `triage_rules.py`, `sla_calculator.py`) y ninguna otra capa las reimplementa.
- Severidad por impacto real (síntoma × radio de afectación × métricas), nunca por urgencia percibida; `tenant_leak` siempre P0.
- SLA: P0 60 min y P1 240 min en reloj 24/7; P2 480 min y P3 1440 min en horario hábil L–V `[08:00, 18:00)` America/Bogota (ADR-002).
- Escalamiento al 75 % (`>=`) si no está `RESOLVED` ni incumplido; incumplimiento con `>`.
- Equipos: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`. Estados: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`.
- Clave de duplicados `<component>:<firma-del-síntoma>` calculada en el dominio.
- Mismas entradas ⇒ mismas salidas: el tiempo de referencia siempre es inyectable.

### II. Arquitectura Hexagonal estricta (ADR-003) — NO NEGOCIABLE

- `src/domain/`: sin imports de frameworks, HTTP, drivers de BD, ORMs ni de capas externas.
- `src/application/`: `ports.py` (puertos `typing.Protocol`, p. ej. `IncidentRepositoryPort`) y `services.py` (`IncidentService`); solo stdlib + `src.domain`.
- `src/adapters/inbound/`: FastAPI y Typer delegan en `IncidentService` y obtienen la persistencia solo vía `src.adapters.outbound.factory`; listos para un futuro adaptador MCP sin duplicar lógica. Toda capacidad expuesta debe tener paridad REST ↔ CLI.
- `src/adapters/outbound/`: implementaciones intercambiables de los puertos, seleccionadas por `DATABASE_URL`.

### III. Especificación BDD y pruebas de aceptación obligatorias

Cada hito parte de un `spec.md` con escenarios `Given / When / Then` en lenguaje de negocio, mapeados 1:1 a funciones `test_bdd_*` en `tests/` (FastAPI `TestClient` y Typer `CliRunner` sobre almacenamiento aislado). Un hito solo se cierra con `uv run pytest -v` al 100 %.

### IV. Persistencia sin ORM detrás de puertos (ADR-001, enmendado por ADR-004)

- SQL parametrizado escrito a mano; **prohibidos los ORMs pesados**.
- Motores soportados: SQLite (`sqlite3` estándar) para desarrollo/pruebas y PostgreSQL vía `psycopg[binary]` para producción, seleccionados por `DATABASE_URL` (`sqlite:///...`, por defecto `sqlite:///:memory:`; `postgresql://...`).
- Marcas temporales en TEXT ISO 8601 en ambos motores para paridad temporal.
- Cualquier otro motor o un ORM requiere un ADR nuevo antes de especificarse.

### V. Verificación determinista y simplicidad

- Fronteras hexagonales verificadas con Ruff (`TID251` banned-api, `TID252` `ban-relative-imports = "parents"`) mediante `ruff.toml` jerárquicos en `src/domain/`, `src/application/` y `src/adapters/inbound/`: `uv run ruff check src/` debe terminar en `All checks passed!`.
- Artefactos concisos: sin requisitos inventados fuera de esta Constitución; YAGNI.

## Restricciones Técnicas

- Python ≥ 3.10 gestionado exclusivamente con `uv` (`uv add`, `uv sync`, `uv run`); `pyproject.toml` y `uv.lock` versionados.
- REST con FastAPI + Pydantic v2; CLI con Typer; servidor ASGI `uvicorn`.
- Runtime de contenedores (ADR-004): imagen `python:3.12-slim` con `uv` y Docker Compose con servicios `api` y `db` (`postgres:16-alpine`).

## Flujo de Desarrollo

1. Orden causal: **ADR → Constitución → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` → `/speckit.implement`**.
2. Plan (solo lectura) antes de Build; curaduría humana de `spec.md`, `plan.md` y `tasks.md` contra la verbosidad.
3. Cierre: `uv run ruff check src/` + `uv run pytest -v` en verde.

## Governance

Esta Constitución prevalece sobre cualquier otro artefacto. Las enmiendas requieren un ADR (o justificación registrada), aumento de versión semántica (MAJOR: se elimina/redefine un principio; MINOR: se añade/amplía; PATCH: redacción) y actualización del Sync Impact Report. `/speckit.analyze` trata cualquier conflicto con un principio como CRÍTICO.

**Version**: 1.1.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-23
