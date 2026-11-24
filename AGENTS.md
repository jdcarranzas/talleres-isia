# AGENTS.md — Manual operativo de IncidentOps

Servicio Python (gestionado con `uv`) para triaje determinista de reportes, cálculo de SLA y ciclo de vida de incidentes, con **Arquitectura Hexagonal** (ADR-003). Este archivo describe *cómo operar el repositorio*; los principios innegociables están en `.specify/memory/constitution.md`.

## Estructura

```text
src/
├── domain/            # Núcleo puro (solo stdlib): models.py, triage_rules.py, sla_calculator.py
├── application/       # ports.py (IncidentRepositoryPort) y services.py (IncidentService)
├── adapters/
│   ├── inbound/       # api/ (FastAPI: schemas.py, app.py:create_app) y cli.py (Typer)
│   └── outbound/      # sqlite_repository.py, postgres_repository.py, factory.py (DATABASE_URL)
├── context_audit.py        # Utilidad heredada de Semana 1 (auditoría de tokens)
└── incident_repository.py  # Benchmark heredado de Semana 1 (anti-patrón N+1, solo referencia)
tests/                 # test_spec_00N_*.py: aceptación BDD 1:1 con specs/
specs/                 # 001 (manual) y 002–004 (Spec Kit: spec.md, plan.md, tasks.md)
docs/                  # ROADMAP.md, constitution.md (borrador manual), adr/ (MADR)
.specify/              # Spec Kit: memory/constitution.md (oficial), templates, scripts (py)
.opencode/             # commands/speckit.*.md y skills/{hexagonal-architecture,bdd-acceptance,adr-writer}
data/sample_incidents.json
```

## Comandos

```bash
uv sync                                   # instala dependencias (incluye dev: pytest, httpx, ruff)
uv run ruff check src/                    # fronteras hexagonales (TID251/TID252) -> All checks passed!
uv run pytest -v                          # aceptación BDD de los hitos 001-004
uv run python -m src.domain.triage_rules  # demo del motor de triaje
uv run python -m src.domain.sla_calculator
uv run python -m src.adapters.inbound.cli --help   # triage | summary | create | sla | health
uv run uvicorn --factory src.adapters.inbound.api.app:create_app --reload --port 8000
docker compose up --build                 # api + db (PostgreSQL 16) -> http://localhost:8000/health
```

- `DATABASE_URL`: `sqlite:///:memory:` (por defecto), `sqlite:///incidentops.db` o `postgresql://user:pass@host:5432/db`.
- Prueba opcional contra PostgreSQL real: `POSTGRES_TEST_URL=postgresql://... uv run pytest -v -k postgres`.

## Reglas de trabajo para el agente

1. Alterna **Plan → Build**: analiza y propone en modo Plan (solo lectura); edita y ejecuta solo en Build tras aprobación.
2. Flujo SDD: ADR (skill `adr-writer`) → `/speckit.constitution` → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` → `/speckit.implement`.
3. Respeta las capas (skill `hexagonal-architecture`) y escribe escenarios/pruebas con la skill `bdd-acceptance`.
4. Dependencias solo con `uv add` / `uv add --dev`; nunca `pip install`.
5. Un cambio está terminado solo con `uv run ruff check src/` y `uv run pytest -v` en verde.
6. No reescribas ADRs aceptados; emite uno nuevo que los reemplace.
