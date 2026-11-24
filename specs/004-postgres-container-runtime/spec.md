# Feature Specification: Persistencia PostgreSQL y runtime en contenedores

**Feature Branch**: `004-postgres-container-runtime`

**Created**: 2026-11-23

**Status**: Implemented

**Input**: User description: "Necesitamos preparar el servicio para ejecutarse en contenedores junto con una base de datos relacional dedicada en producción y exponer un chequeo real de salud de conectividad." (Respaldado por ADR-004 y Constitución v1.1.0.)

## Clarifications

### Session 2026-11-23

- Q: ¿Qué significa "chequeo real"? → A: Ejecutar `SELECT 1` contra la base configurada en cada consulta; no un *ping* estático del proceso.
- Q: ¿Contrato del chequeo? → A: `GET /health` → `200 {"status": "ok", "database": "connected"}` o `503 {"status": "error", "database": "unavailable"}`; CLI `health` con el mismo JSON y código `0`/`1`.
- Q: ¿Cómo se elige el motor? → A: Solo por `DATABASE_URL`: `postgresql://...` → PostgreSQL; `sqlite:///...` o variable ausente → SQLite (`:memory:` por defecto). Un esquema no soportado falla explícitamente al arrancar.
- Q: ¿Las pruebas necesitan Docker? → A: No. La suite completa corre sobre SQLite; la integración con PostgreSQL real es opcional (`POSTGRES_TEST_URL`).
- Q: ¿Cuántos contenedores y en qué orden arrancan? → A: Dos (`api`, `db`); `api` espera a que `db` esté sana (`pg_isready`) y a su vez se declara sana solo si `/health` responde `200`.
- Q: ¿Dónde viven las credenciales? → A: Variables de entorno con valores de desarrollo por defecto en Compose, sobrescribibles con `.env` (no versionado).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chequeo real de salud (Priority: P1)

Plataforma necesita saber si el servicio puede hablar con su base de datos, no solo si el proceso está vivo.

**Independent Test**: Con la base disponible responde 200; con la base caída responde 503.

**Acceptance Scenarios**:

1. **Given** una base de datos configurada y disponible, **When** Plataforma consulta `GET /health` o soporte ejecuta `health` por CLI, **Then** se ejecuta una consulta real sobre la base y la respuesta es `200` / código `0` con `{"status": "ok", "database": "connected"}`.
2. **Given** que la persistencia no logra conectar con la base, **When** se consulta `GET /health`, **Then** responde `503 Service Unavailable` con `{"status": "error", "database": "unavailable"}` (y la CLI termina con código `1`).

### User Story 2 - Selección transparente del motor (Priority: P1)

Desarrollo trabaja sin contenedores y producción usa una base dedicada, con el mismo código.

**Acceptance Scenarios**:

1. **Given** `DATABASE_URL=postgresql://...`, **When** el servicio arranca, **Then** usa la base PostgreSQL; **given** `sqlite:///...` o la variable ausente, **then** usa SQLite (en memoria por defecto); en ambos casos se cumple el mismo contrato de persistencia.

### User Story 3 - Orquestación reproducible (Priority: P2)

Plataforma levanta el sistema completo con un solo comando.

**Acceptance Scenarios**:

1. **Given** el repositorio clonado, **When** se ejecuta `docker compose up --build`, **Then** se levantan dos contenedores: `db` (`postgres:16-alpine`, volumen persistente, healthcheck `pg_isready`) y `api` (imagen `python:3.12-slim` con `uv`, `DATABASE_URL` apuntando a `db`, `depends_on` con `service_healthy` y healthcheck sobre `/health`), y `http://localhost:8000/health` responde `200`.

### Edge Cases

- `DATABASE_URL` con esquema no soportado (p. ej. `mysql://`) → error explícito.
- Base reiniciada mientras la API corre → `/health` pasa a `503` y se recupera sin reiniciar la API.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST exponer `GET /health` y CLI `health` con el contrato clarificado.
- **FR-002**: El chequeo MUST ejecutar `SELECT 1` real contra el motor configurado.
- **FR-003**: El sistema MUST seleccionar el motor solo a partir de `DATABASE_URL`.
- **FR-004**: Ambos motores MUST cumplir el mismo contrato de persistencia y producir resultados de SLA idénticos.

### Non-Functional Requirements

- **RNF-001 Reproducibilidad**: imagen construida con `uv sync --frozen` sobre `uv.lock`, sin dependencias de desarrollo.
- **RNF-002 Disponibilidad**: orden de arranque garantizado por healthchecks; reinicio `unless-stopped`.
- **RNF-003 Durabilidad**: datos de PostgreSQL en volumen con nombre.
- **RNF-004 Seguridad**: contenedor `api` sin root; SQL siempre parametrizado; credenciales por entorno.
- **RNF-005 Rapidez del feedback**: `uv run pytest -v` completo sin Docker en segundos.
- **RNF-006 Sin ORM**: driver `psycopg[binary]` con SQL explícito (ADR-004).

### Key Entities

- **Estado de salud**: estado del servicio y de la conectividad con la base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los 4 escenarios pasan como pruebas automatizadas sin daemon Docker.
- **SC-002**: `docker compose config -q` valida la definición y `/health` responde `200` tras `docker compose up --build`.

## Assumptions

- Un solo nodo PostgreSQL (sin réplicas) es suficiente para este hito.
- No se requiere herramienta de migraciones: el esquema se crea con `CREATE ... IF NOT EXISTS` al primer uso.
