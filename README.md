# IncidentOps

Servicio Python gestionado con [`uv`](https://docs.astral.sh/uv/) para **triaje determinista de reportes**, **SLA en horario hábil** y **ciclo de vida de incidentes** (registro, duplicados abiertos, auditoría de SLA), construido con **Arquitectura Hexagonal** y **Spec-Driven Development** (GitHub Spec Kit + OpenCode).

Curso: *Ingeniería de Software Asistida por IA (ISIA)* — Semana 2.

## Inicio rápido

```bash
uv sync
uv run ruff check src/
uv run pytest -v
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en todas las transacciones de la pasarela de pagos"
uv run uvicorn --factory src.adapters.inbound.api.app:create_app --port 8000   # http://localhost:8000/docs
docker compose up --build                                                        # api + PostgreSQL 16
```

| Interfaz | REST | CLI |
| :--- | :--- | :--- |
| Triaje (H001) | `POST /api/v1/incidents/triage` | `triage` |
| Resumen activos (H002) | `GET /api/v1/incidents/summary` | `summary` |
| Registro + duplicados (H003) | `POST /api/v1/incidents` | `create` |
| Auditoría SLA (H003) | `GET /api/v1/incidents/{id}/sla` | `sla` |
| Salud (H004) | `GET /health` | `health` |

## Mapa de artefactos

- Operación del repositorio: [`AGENTS.md`](AGENTS.md) · Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Constitución: [`.specify/memory/constitution.md`](.specify/memory/constitution.md) (oficial) y [`docs/constitution.md`](docs/constitution.md) (borrador manual)
- Decisiones: [`docs/adr/`](docs/adr/) (ADR-001 a ADR-004, MADR estricto)
- Especificaciones: [`specs/`](specs/) · Skills: [`.opencode/skills/`](.opencode/skills/) · Bitácora: [`SDD_LOG.md`](SDD_LOG.md)

Los entregables de la Semana 1 se conservan en `Entrega/` y `src/context_audit.py` / `src/incident_repository.py`.
