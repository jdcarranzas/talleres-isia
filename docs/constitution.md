# Constitución de IncidentOps (versión manual — Iteración 1)

> Borrador manual redactado en la Iteración 1 a partir de `docs/ROADMAP.md` y `docs/adr/003-arquitectura-hexagonal.md`.
> La versión **oficial y vigente** es `.specify/memory/constitution.md` (formalizada con `/speckit.constitution` y enmendada por ADR-004).

## 1. Dominio determinista único

- **Triaje**: la severidad se decide por **impacto real** (síntoma × radio de afectación × métricas), nunca por urgencia percibida; palabras como "urgente" u "hoy" solo se registran en el `rationale`. Una fuga entre organizaciones (`tenant_leak`) siempre es P0.
- **Severidades y SLA**: P0 = 60 min y P1 = 240 min en reloj **24/7**; P2 = 480 min y P3 = 1440 min solo en **horario hábil L–V 08:00–18:00** (America/Bogota, ventana `[08:00, 18:00)`), según ADR-002.
- **Escalamiento**: `requires_escalation` cuando el consumo alcanza el **75 %** del SLA (`>=`), el incidente no está `RESOLVED` y aún no incumple; incumple con `>` al máximo.
- **Equipos válidos**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM` (síntomas de seguridad → `Security-IAM`).
- **Estados**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`.
- **Clave de duplicados**: `<component>:<firma-del-síntoma>` calculada solo en el dominio.
- Estas reglas viven **exclusivamente** en `src/domain/`; ninguna capa externa las reimplementa.

## 2. Arquitectura Hexagonal (ADR-003)

- `src/domain/`: núcleo puro (solo biblioteca estándar).
- `src/application/`: puertos secundarios `typing.Protocol` (`ports.py`) y casos de uso compartidos (`services.py`, `IncidentService`).
- `src/adapters/inbound/`: adaptadores primarios (API REST y CLI) que **solo** delegan en `IncidentService`; el núcleo queda listo para un futuro adaptador MCP sin duplicar lógica.
- `src/adapters/outbound/`: adaptadores secundarios intercambiables que implementan los puertos.
- Las dependencias apuntan siempre hacia el dominio.

## 3. Gobernanza técnica y calidad

- Python ≥ 3.10 gestionado con `uv` (`uv add`, `uv run`); `pyproject.toml` + `uv.lock` versionados.
- FastAPI + Pydantic v2 para REST; Typer para CLI.
- SQLite3 estándar sin ORMs pesados (ADR-001); cualquier cambio de motor requiere un ADR previo.
- Toda funcionalidad nace de una especificación BDD (`Given / When / Then`) y se acepta con pruebas automatizadas en `pytest` (`uv run pytest -v`).
- Orden causal obligatorio: **ADR → Constitución → Especificación → Plan → Código**.
