# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`)

**Estudiante(s)**: `[Nombre completo]`
**Fecha**: `2026-11-23`
**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `Claude Opus 5.5 (Anthropic) con razonamiento extendido para clarify / plan / analyze y redacción de ADRs; el mismo modelo en modo de ejecución directa para implement. GitHub Spec Kit 1.4.4 (specify init --here --integration opencode --script py) generó .specify/ y .opencode/commands/; los artefactos se produjeron siguiendo esas plantillas y comandos.`

> Nota de transparencia: en esta sesión el agente no fue la TUI de OpenCode sino Claude operando sobre el mismo repositorio con las mismas plantillas de Spec Kit. Si se re-ejecutan los comandos `/speckit.*` dentro de OpenCode, actualizar esta línea con el modelo usado allí.

---

## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze`

### 1.1 Feature `003-incident-lifecycle-sla`
- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:
  1. *"Equivalente abierto" no estaba definido*: se fijó como misma `duplicate_group_key` en `OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`, excluyendo `RESOLVED` **y el propio ID recién creado**. Sin la segunda exclusión, reenviar un incidente con el mismo `incident_id` lo marcaba como duplicado de sí mismo.
  2. *Choque de definiciones de "activo" entre hitos*: H002 llama activo solo a `OPEN`/`IN_PROGRESS`, mientras que H003 trata `ESCALATION_REQUIRED` como abierto. Se resolvió con dos constantes de dominio distintas (`ACTIVE_STATUSES` y `OPEN_STATUSES`) en lugar de una sola lista ambigua.
  3. *Marcas temporales naive vs. aware*: la API recibe `2026-11-06T17:00:00` (sin zona) y el reloj interno produce fechas con zona; compararlas lanzaba `TypeError`. Se acordó interpretar las naive como America/Bogota y normalizar todo (`normalize_timestamp`) antes de comparar y persistir.
  4. *Reenvío del mismo `incident_id`*: ¿error 409 o actualización? Se eligió *upsert* (último valor gana), coherente con `INSERT ... ON CONFLICT DO UPDATE` que exige el Hito 004.
  5. *`reference_time < created_at` en un incidente ya resuelto*: se audita contra `resolved_at` y no se rechaza, porque la referencia se ignora para incidentes cerrados.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - Cobertura 1:1 escenario ↔ prueba: los 5 escenarios del `spec.md` tienen su `test_bdd_s*`; se añadió `s4b` porque el escenario 4 de la guía mezclaba dos verificaciones (404 y 422) y la validación de campos vacíos del registro no tenía prueba.
  - Constitución: el plan no añade reglas en adaptadores; la clave de duplicados y los estados viven en `src/domain/models.py`. Sin hallazgos CRÍTICOS.
  - Inconsistencia de terminología corregida: el plan hablaba de "estados abiertos" y el spec de "equivalente abierto"; se unificó en el spec.

### 1.2 Feature `004-postgres-container-runtime`
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**:
  1. *"Chequeo real"*: se exigió `SELECT 1` contra el motor en cada consulta (no un *ping* del proceso) y una conexión por operación, para que `/health` pase a 503 cuando la base cae y se recupere solo, sin reiniciar la API.
  2. *Pruebas sin Docker (RNF-005)*: el adaptador PostgreSQL crea su esquema de forma perezosa, así que construirlo no abre conexión; eso permite verificar la conformidad con `IncidentRepositoryPort` y la selección por `DATABASE_URL` sin base. La integración real queda opcional con `POSTGRES_TEST_URL`.
  3. *Paridad temporal entre motores*: fechas como TEXT ISO 8601 **con zona** en ambos motores (ADR-004); así el cálculo de SLA es idéntico en SQLite y PostgreSQL.
  4. *Orden de arranque y salud*: `api` depende de `db` con `service_healthy` (`pg_isready`) y se declara sana solo si `/health` responde 200 (el healthcheck usa `urllib` porque `python:3.12-slim` no trae `curl`).
  5. *Seguridad*: contenedor sin root, credenciales por variables de entorno con valores de desarrollo sobrescribibles por `.env`, SQL siempre parametrizado (`%s`).
  6. *Esquemas no soportados* (`mysql://`): error explícito al construir el repositorio en lugar de caer silenciosamente a SQLite.

---

## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos)

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) |
| :--- | :--- | :--- |
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | Un solo `001-triage-endpoint-manual.md` mezcla negocio con contratos HTTP/CLI; el plan y las tareas quedaron en el chat del modo Plan y **no son versionables ni auditables**. | `spec.md` (qué/por qué), `plan.md` (cómo, con *Constitution Check*) y `tasks.md` (orden y dependencias) separados por plantilla; cada decisión tiene un archivo donde vivir. |
| **Gestión de ambigüedades (`/speckit.clarify`)** | Dependió de recordar pedir "hazme preguntas antes de escribir". Las decisiones quedaron como tabla añadida a mano. | Sección `## Clarifications` con preguntas → respuestas fechadas dentro del spec; detectó casos que la guía no mencionaba (auto-duplicado, naive/aware, `ESCALATION_REQUIRED`). |
| **Consistencia contra la Constitución (`/speckit.analyze`)** | Ninguna garantía automática: la revisión fue humana y de memoria. | *Constitution Check* obligatorio en cada `plan.md` + análisis cruzado spec↔plan↔tasks; reforzado por Ruff (fronteras) y pytest (comportamiento) como verificación determinista. |
| **Riesgo de verbosidad / exceso de Markdown** | Bajo: un archivo corto, pero con conocimiento perdido en el chat. | Alto por defecto: la plantilla de plan pide `research.md`, `data-model.md`, `contracts/` y `quickstart.md`. Se condensaron en una sección *Design Notes* de `plan.md` y se eliminaron los ejemplos de la plantilla de tareas. |

- **Análisis basado en MartinFowler.com (Birgitta Böckeler)**:
  1. **Nivel: *Spec-first*, con rasgos de *spec-anchored*.** Las specs se escriben antes del código y guían la implementación, y se conservan versionadas junto al código con pruebas `test_bdd_*` que las anclan 1:1. Pero no es *spec-anchored* pleno: si mañana cambia el código nada obliga a actualizar el `spec.md` (las pruebas fallarían, la spec no), y la evolución de un hito se haría con una spec nueva más que editando la anterior. Está lejos de *spec-as-source*: el código sigue siendo el artefacto que se mantiene a mano y la spec no se regenera en código.
  2. **Técnicas contra las "montañas de Markdown"**: (a) `docs/ROADMAP.md` es una sola tabla de 4 filas sin detalles técnicos; (b) en `clarify` se registraron solo decisiones que cambian el comportamiento, cada una en una línea; (c) en `plan` se condensaron research/data-model/contracts en notas breves y la estructura de código se limitó a los archivos tocados; (d) `tasks.md` de 12–14 tareas por hito, sin las tareas de ejemplo de la plantilla; (e) los ADRs siguen MADR estricto sin listas de archivos ni pasos de verificación; (f) sobre todo, **no se aprobó nada sólo por leerlo**: cada escenario tiene una prueba determinista (`uv run pytest -v`) y cada frontera una regla de Ruff (`uv run ruff check src/`). La evidencia ejecutable sustituye la lectura exhaustiva. Un hallazgo concreto: la orden de verificación de la guía (`triage --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"`) devuelve **P1**, no P0, porque el texto no tiene señal de alcance global; la spec la aceptaba sin cuestionarla y fue la ejecución la que mostró que el escenario necesitaba el reporte completo ("en todas las transacciones… ningún comercio puede cobrar").

---

## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning*
- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-architecture`, `bdd-acceptance`, `adr-writer`)**: los *commands* de `.opencode/commands/` son flujos explícitos que el humano dispara (`/speckit.plan` ejecuta el script `setup_plan.py`, llena `plan.md` desde la plantilla y aplica la Constitución); son el *proceso*. Las *skills* de `.opencode/skills/` son *conocimiento* bajo demanda: OpenCode indexa solo su `name` y `description` al inicio y carga el `SKILL.md` completo cuando la tarea encaja (p. ej. al tocar `src/` se activa `hexagonal-architecture`; al escribir escenarios, `bdd-acceptance`), sin inflar `AGENTS.md` en cada turno. Por eso las `description` están redactadas como disparadores ("úsala antes de crear, mover o revisar código en `src/`…"). El orden causal **ADR → Constitución → Hito** importa porque la Constitución solo debe *adoptar* decisiones ya justificadas: `ADR-003` comparó capas acopladas vs. hexagonal antes de que `docs/constitution.md` la volviera innegociable; y en el Reto 2, sin `ADR-004` y la enmienda v1.1.0, `/speckit.analyze` habría marcado `psycopg` como violación CRÍTICA del principio "solo `sqlite3`" de ADR-001. Si se invierte el orden, la spec 004 nace en conflicto con su propia Constitución o la Constitución se reescribe a posteriori para justificar el código.
- **Valor de la Arquitectura Hexagonal**: PostgreSQL entró sin tocar `src/domain/` ni la forma de `IncidentRepositoryPort`: bastó un archivo nuevo (`postgres_repository.py`) y dos líneas en `factory.py`. El puerto se declaró completo en H002 (5 métodos), así que H003 y H004 no cambiaron el contrato. FastAPI y Typer llaman al mismo método de `IncidentService` y serializan con los mismos modelos de `schemas.py`, por lo que la paridad REST↔CLI no depende de disciplina sino de estructura; la prueba es que la misma suite pasa sobre SQLite y PostgreSQL (29/29 con `POSTGRES_TEST_URL`). Ruff convierte las fronteras en errores (`TID251`: p. ej. `import psycopg` en `inbound` o `src.adapters` en `application`). Un futuro adaptador MCP sería un tercer módulo en `src/adapters/inbound/` que llama a `IncidentService`, sin duplicar reglas.
- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**: aportó más en `/speckit.clarify` (encontró el auto-duplicado por *upsert*, el conflicto `ACTIVE` vs. `OPEN` y el `TypeError` naive/aware, que no estaban en el enunciado), en `/speckit.plan` (decidir el esquema perezoso para probar PostgreSQL sin base y la conexión por operación para un `/health` honesto) y en la redacción de ADRs (buscar opciones reales y no *strawmen*). En `/speckit.implement` un modelo rápido basta, porque las tareas ya son atómicas y la verificación es determinista: si algo sale mal lo detectan Ruff y pytest, no el razonamiento.

---

## 4. Evidencia de Verificación Determinista
- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**:
```text
All checks passed!
```
  Comprobación de que las reglas sí bloquean violaciones (código inyectado por `--stdin-filename`):
```text
src/domain/x.py: import sqlite3                    -> TID251 `sqlite3` is banned: src/domain no accede a la BD; use IncidentRepositoryPort (ADR-003).
src/application/x.py: from src.adapters... import  -> TID251 `src.adapters` is banned: La aplicación no depende de adaptadores concretos (ADR-003).
src/adapters/inbound/x.py: from src.adapters.outbound.sqlite_repository import ... -> TID251 ... Use src.adapters.outbound.factory.create_repository (ADR-004).
src/adapters/inbound/api/x.py: import psycopg      -> TID251 `psycopg` is banned ... (ADR-004).
src/domain/x.py: from ..adapters import cli        -> TID252 Prefer absolute imports over relative imports from parent modules
```
- **Salida completa de `uv run pytest -v`** (con `POSTGRES_TEST_URL` apuntando a PostgreSQL 16.2 local; sin esa variable el resultado es `28 passed, 1 skipped`):
```text
============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-9.2.0, pluggy-1.7.0 -- ~/venv/bin/python
cachedir: .pytest_cache
rootdir: <repo>
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 29 items

tests/test_spec_001_triage.py::test_bdd_s1_caida_critica_502_en_pasarela_de_pagos_es_p0 PASSED [  3%]
tests/test_spec_001_triage.py::test_bdd_s2_cuenta_individual_bloqueada_con_hoy_no_es_falso_p0 PASSED [  6%]
tests/test_spec_001_triage.py::test_bdd_s3_entradas_vacias_o_solo_espacios_son_rechazadas[body0] PASSED [ 10%]
tests/test_spec_001_triage.py::test_bdd_s3_entradas_vacias_o_solo_espacios_son_rechazadas[body1] PASSED [ 13%]
tests/test_spec_001_triage.py::test_bdd_s3_entradas_vacias_o_solo_espacios_son_rechazadas[body2] PASSED [ 17%]
tests/test_spec_001_triage.py::test_bdd_s4_paridad_cli_triage PASSED     [ 20%]
tests/test_spec_001_triage.py::test_bdd_s4b_cli_triage_rechaza_texto_vacio PASSED [ 24%]
tests/test_spec_002_summary.py::test_bdd_s1_resumen_global_excluye_resueltos PASSED [ 27%]
tests/test_spec_002_summary.py::test_bdd_s2_resumen_filtrado_por_componente PASSED [ 31%]
tests/test_spec_002_summary.py::test_bdd_s3_sin_incidentes_activos_devuelve_resumen_vacio PASSED [ 34%]
tests/test_spec_002_summary.py::test_bdd_s4_resumen_equivalente_por_cli PASSED [ 37%]
tests/test_spec_002_summary.py::test_sqlite_repository_cumple_incident_repository_port PASSED [ 41%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s1_registro_inicial_sin_duplicados PASSED [ 44%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s2_detecta_duplicado_abierto_e_ignora_resueltos PASSED [ 48%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s3_auditoria_sla_en_horario_habil PASSED [ 51%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s4_sla_de_incidente_inexistente_o_referencia_anterior PASSED [ 55%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s4b_registro_rechaza_campos_vacios PASSED [ 58%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_s5_operacion_equivalente_por_cli PASSED [ 62%]
tests/test_spec_004_runtime_health.py::test_bdd_s1_health_operativo_con_select_1_real PASSED [ 65%]
tests/test_spec_004_runtime_health.py::test_bdd_s1b_health_por_cli PASSED [ 68%]
tests/test_spec_004_runtime_health.py::test_bdd_s2_health_ante_fallo_de_conectividad_responde_503 PASSED [ 72%]
tests/test_spec_004_runtime_health.py::test_bdd_s2b_health_cli_falla_con_postgres_inalcanzable PASSED [ 75%]
tests/test_spec_004_runtime_health.py::test_bdd_s3_seleccion_transparente_por_database_url[postgresql://incidentops:secret@db:5432/incidentops-PostgresIncidentRepository] PASSED [ 79%]
tests/test_spec_004_runtime_health.py::test_bdd_s3_seleccion_transparente_por_database_url[postgres://incidentops:secret@db:5432/incidentops-PostgresIncidentRepository] PASSED [ 82%]
tests/test_spec_004_runtime_health.py::test_bdd_s3_seleccion_transparente_por_database_url[sqlite:///:memory:-SQLiteIncidentRepository] PASSED [ 86%]
tests/test_spec_004_runtime_health.py::test_bdd_s3_seleccion_transparente_por_database_url[-SQLiteIncidentRepository] PASSED [ 89%]
tests/test_spec_004_runtime_health.py::test_bdd_s3b_database_url_no_soportada_falla_explicitamente PASSED [ 93%]
tests/test_spec_004_runtime_health.py::test_bdd_s4_orquestacion_reproducible_en_dos_contenedores PASSED [ 96%]
tests/test_spec_004_runtime_health.py::test_postgres_repository_contra_base_real PASSED [100%]

=============================== warnings summary ===============================
../../venv/lib/python3.10/site-packages/fastapi/testclient.py:1
  ~/venv/lib/python3.10/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 29 passed, 1 warning in 0.48s =========================
```
- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose up --build`)**:
```text
$ uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"
{
  "incident_id": "INC-1001",
  "severity": "P1",
  "component": "payments-gateway",
  "recommended_team": "Backend-Core",
  "symptom_category": "http_5xx",
  "impact_scope": "shared",
  "rationale": "errores 5xx parciales en un servicio compartido; alcance=shared",
  "consistency_ratio": 1.0,
  "duplicate_group_key": "payments-gateway:http-502-outage"
}

$ uv run python -m src.adapters.inbound.cli summary
{
  "reference_time": "2026-11-09T12:00:00-05:00",
  "component": null,
  "total_active": 0,
  "breached_count": 0,
  "incidents": []
}

$ uv run python -m src.adapters.inbound.cli health
{
  "status": "ok",
  "database": "connected"
}
(exit=0)

# --- Persistencia PostgreSQL real (DATABASE_URL=postgresql://...) ---
$ ... health
{
  "status": "ok",
  "database": "connected"
}
(exit=0)
$ ... create --incident-id INC-2002 --title "Cuenta bloqueada" --raw-text "<INC-1002>" --created-at 2026-11-06T17:00:00
{
  "incident_id": "INC-2002",
  "severity": "P2",
  "component": "auth-identity",
  "recommended_team": "Security-IAM",
  "symptom_category": "auth",
  "impact_scope": "individual",
  "rationale": "bloqueo operativo que afecta a un usuario individual; alcance=individual; términos de urgencia ignorados: hoy",
  "consistency_ratio": 1.0,
  "duplicate_group_key": "auth-identity:auth",
  "title": "Cuenta bloqueada",
  "status": "OPEN",
  "created_at": "2026-11-06T17:00:00-05:00",
  "is_duplicate": false,
  "duplicate_of": []
}
$ ... create --title "Cuenta bloqueada otra vez" --raw-text "<mismo reporte>"
  "incident_id": "INC-8F57196A",
  "severity": "P2",
  "duplicate_group_key": "auth-identity:auth",
  "is_duplicate": true,
    "INC-2002"
$ ... sla --incident-id INC-2002 --reference-time 2026-11-09T09:00:00
{
  "incident_id": "INC-2002",
  "severity": "P2",
  "elapsed_minutes": 120,
  "allowed_minutes": 480,
  "remaining_minutes": 360,
  "is_breached": false,
  "requires_escalation": false
}
$ ... summary --component auth-identity --reference-time 2026-11-09T09:00:00
{
  "reference_time": "2026-11-09T09:00:00-05:00",
  "component": "auth-identity",
  "total_active": 2,
  "breached_count": 0,
  "incidents": [
    {
      "incident_id": "INC-2002",
      "title": "Cuenta bloqueada",
      "component": "auth-identity",
      "severity": "P2",
      "status": "OPEN",
      "elapsed_minutes": 120,
      "is_breached": false,
      "requires_escalation": false
    },
    {
      "incident_id": "INC-8F57196A",
      "title": "Cuenta bloqueada otra vez",
      "component": "auth-identity",
      "severity": "P2",
      "status": "OPEN",
      "elapsed_minutes": 30,
      "is_breached": false,
      "requires_escalation": false
    }
  ]
}
$ ... sla --incident-id INC-NOPE
{"error": "No existe el incidente 'INC-NOPE'."}
(exit=1)

# --- PostgreSQL detenido / inalcanzable ---
$ ... health
{
  "status": "error",
  "database": "unavailable"
}
(exit=1)
```
  API REST servida con `uv run uvicorn --factory src.adapters.inbound.api.app:create_app`:
```text
$ curl -s -w "\nHTTP %{http_code}\n" localhost:8765/health
{"status":"ok","database":"connected"}
HTTP 200
$ curl -s -X POST localhost:8765/api/v1/incidents/triage -d {"incident_id":"INC-1","raw_text":"   "}
ext"],"msg":"Value error, no puede estar vacío ni contener solo espacios","input":"   ","ctx":{"error":{}}}]}
HTTP 422

$ curl -s -X POST localhost:8765/api/v1/incidents -d {"incident_id":"INC-1001","title":"Caída pagos","raw_text":"<INC-1001>","created_at":"2026-11-09T10:00:00"}
{"incident_id":"INC-1001","severity":"P0","component":"payments-gateway","recommended_team":"Backend-Core","symptom_category":"http_5xx","impact_scope":"global","rationale":"indisponibilidad global de un servicio crítico; alcance=global; términos de urgencia ignorados: urgente","consistency_ratio":1.0,"duplicate_group_key":"payments-gateway:http-502-outage","title":"Caida pagos","status":"OPEN","created_at":"2026-11-09T10:00:00-05:00","is_duplicate":false,"duplicate_of":[]}
HTTP 201
$ curl -s "localhost:8765/api/v1/incidents/INC-1001/sla?reference_time=2026-11-09T09:00:00"
{"detail":"reference_time no puede ser anterior a created_at del incidente."}
HTTP 422
$ curl -s "localhost:8765/api/v1/incidents/summary?reference_time=2026-11-09T12:00:00"
{"reference_time":"2026-11-09T12:00:00-05:00","component":null,"total_active":1,"breached_count":1,"incidents":[{"incident_id":"INC-1001","title":"Caida pagos","component":"payments-gateway","severity":"P0","status":"OPEN","elapsed_minutes":120,"is_breached":true,"requires_escalation":false}]}
HTTP 200
```
  Dominio y benchmark heredado:
```text
$ uv run python -m src.domain.triage_rules  (grupos)
Grupos por duplicate_group_key:
  payments-gateway:http-502-outage   P0  Backend-Core  INC-1001, INC-1006  [RECURRENTE]
  reporting-api:tenant_leak          P0  Security-IAM  INC-1007
  database-cluster:connection_pool   P1  Data-DBA      INC-1005
  reporting-api:latency              P2  Data-DBA      INC-1003, INC-1008  [RECURRENTE]
  auth-identity:auth                 P2  Security-IAM  INC-1002
  reporting-api:export_latency       P2  Data-DBA      INC-1009
  frontend-ui:ui                     P3  Platform-SRE  INC-1004
  infra-certificates:cert_expiry     P3  Platform-SRE  INC-1010

$ uv run python -m src.domain.sla_calculator  (cierre)
----------------------------------------------------------------------------------------------------------------------------
Todos los casos OK.

$ uv run python -m src.incident_repository --records 10000
=== Resultado del Benchmark (Antes de Refactorizar) ===
Incidentes activos encontrados para 'payments-gateway': 800
Tiempo total (20 ejecuciones sobre 10000 filas): 216.88 ms
```
  **`docker compose up --build`** (ejecutado en Windows con Docker Desktop; se omiten las líneas de descarga de capas):
```text
$ docker compose up --build
[+] Building 27.9s (17/17) FINISHED
 => [internal] load metadata for ghcr.io/astral-sh/uv:0.13.8                                1.4s
 => [internal] load metadata for docker.io/library/python:3.12-slim                         6.7s
 => [stage-0 2/8] COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/                    0.2s
 => [stage-0 3/8] WORKDIR /app                                                              0.1s
 => [stage-0 4/8] COPY pyproject.toml uv.lock ./                                            0.1s
 => [stage-0 5/8] RUN uv sync --frozen --no-dev --no-install-project                        2.3s
 => [stage-0 6/8] COPY src ./src                                                            0.1s
 => [stage-0 7/8] COPY data ./data                                                          0.1s
 => [stage-0 8/8] RUN useradd --create-home --uid 10001 incidentops && chown -R incidentops /app   9.4s
 => => naming to docker.io/library/starter-project-api:latest                               0.0s
[+] up 18/18
 ✔ Image postgres:16-alpine        Pulled                                                  11.9s
 ✔ Image starter-project-api       Built                                                   28.0s
 ✔ Network starter-project_default Created                                                  0.0s
 ✔ Volume starter-project_pgdata   Created                                                  0.0s
 ✔ Container starter-project-db-1  Created                                                  0.2s
 ✔ Container starter-project-api-1 Created                                                  0.1s
Attaching to api-1, db-1
Container starter-project-db-1 Waiting
db-1  | PostgreSQL init process complete; ready for start up.
db-1  | 2026-11-24 02:17:04.320 UTC [1] LOG:  starting PostgreSQL 16.16 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
db-1  | 2026-11-24 02:17:04.321 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
db-1  | 2026-11-24 02:17:04.341 UTC [1] LOG:  database system is ready to accept connections
Container starter-project-db-1 Healthy
api-1  | INFO:     Started server process [1]
api-1  | INFO:     Waiting for application startup.
api-1  | INFO:     Application startup complete.
api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
api-1  | INFO:     127.0.0.1:40706 - "GET /health HTTP/1.1" 200 OK
api-1  | INFO:     127.0.0.1:41808 - "GET /health HTTP/1.1" 200 OK
api-1  | INFO:     127.0.0.1:60518 - "GET /health HTTP/1.1" 200 OK
```
  Lectura de la evidencia: `api` solo arrancó después de `Container starter-project-db-1 Healthy` (`depends_on: service_healthy` con `pg_isready`), y las peticiones `GET /health` desde `127.0.0.1` son el *healthcheck* del propio contenedor `api`, que ejecuta `SELECT 1` real contra PostgreSQL 16.16 y responde `200 OK`. El volumen `starter-project_pgdata` se creó para persistir los datos.

  **Validación de Compose, salud desde el host, CLI dentro del contenedor y caída/recuperación de la base** (segunda terminal, con los contenedores corriendo):
```text
PS> docker compose config -q; if ($?) { "Compose OK" }
Compose OK

PS> curl.exe -i http://localhost:8000/health
HTTP/1.1 200 OK
date: Tue, 24 Nov 2026 02:24:11 GMT
server: uvicorn
content-length: 38
content-type: application/json

{"status":"ok","database":"connected"}

PS> docker compose exec -T api python -m src.adapters.inbound.cli health
{
  "status": "ok",
  "database": "connected"
}

PS> docker compose stop db
[+] stop 1/1
 ✔ Container starter-project-db-1 Stopped                                    0.3s

PS> curl.exe -i http://localhost:8000/health
HTTP/1.1 503 Service Unavailable
date: Tue, 24 Nov 2026 02:24:24 GMT
server: uvicorn
content-length: 43
content-type: application/json

{"status":"error","database":"unavailable"}

PS> docker compose start db
[+] start 1/1
 ✔ Container starter-project-db-1 Started                                    0.2s
```
  Con esto quedan verificados en contenedores los 4 escenarios de la Feature 004: `200` con `SELECT 1` real (escenario 1, API y CLI), `503` al caer la base (escenario 2), selección de PostgreSQL por `DATABASE_URL` dentro de `api` (escenario 3) y orquestación `db` + `api` con healthchecks (escenario 4). La API no se reinició entre la caída y el regreso de la base, lo que confirma la decisión de abrir una conexión por operación.

  **Persistencia del volumen** (segundo `docker compose up --build`, con la imagen en caché):
```text
 => CACHED [stage-0 5/8] RUN uv sync --frozen --no-dev --no-install-project      0.0s
[+] up 1/1
 ✔ Image starter-project-api Built                                               1.8s
db-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
db-1  | 2026-11-24 02:22:37.250 UTC [1] LOG:  database system is ready to accept connections
Container starter-project-db-1 Healthy
api-1  | INFO:     Application startup complete.
api-1  | INFO:     127.0.0.1:49180 - "GET /health HTTP/1.1" 200 OK
```

  Validación estructural adicional del `docker-compose.yml` (PyYAML):
```text
services: ['api', 'db']
db.image: postgres:16-alpine
db.healthcheck: ['CMD-SHELL', 'pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}']
api.depends_on: {'db': {'condition': 'service_healthy'}}
volumes: ['pgdata']
```
