# Feature Specification: Ciclo de vida, duplicados y auditoría de SLA

**Feature Branch**: `003-incident-lifecycle-sla`

**Created**: 2026-11-23

**Status**: Implemented

**Input**: User description: "Necesitamos guardar los incidentes cuando llegan, avisar si ya había otro equivalente abierto, y consultar cómo va su SLA tanto por API como desde nuestra herramienta CLI."

## Clarifications

### Session 2026-11-23

- Q: ¿Qué campos son obligatorios al registrar? → A: `title` y `raw_text`; vacíos o solo espacios se rechazan (`422` en API, código `1` en CLI).
- Q: ¿Y los opcionales? → A: `incident_id` (si se omite se genera `INC-<HEX8>`), `created_at` (instante actual si se omite) y `status` (por defecto `OPEN`; solo estados válidos de la Constitución).
- Q: ¿Qué devuelve el registro? → A: `201 Created` (API) o JSON (CLI) con la clasificación completa del triaje, `is_duplicate` (bool) y `duplicate_of` (lista de IDs).
- Q: ¿Qué es exactamente un "equivalente abierto"? → A: otro incidente con la misma clave de duplicados en estado `OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`; se excluyen los `RESOLVED` y el propio identificador recién creado.
- Q: ¿Cómo se audita el SLA? → A: `GET /api/v1/incidents/{incident_id}/sla` y CLI `sla`, con `reference_time` opcional (ISO 8601); `404` si el incidente no existe; `422` si `reference_time` es anterior a `created_at` (código `1` en CLI).
- Q: ¿Qué pasa si se reenvía un `incident_id` existente? → A: Se actualiza el registro (último valor gana); no se trata como duplicado de sí mismo.
- Q: ¿Fechas con y sin zona horaria? → A: Se aceptan ambas; las que no traen zona se interpretan en hora de negocio (America/Bogota).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar incidentes y detectar duplicados abiertos (Priority: P1)

Operaciones registra cada reporte entrante y necesita saber de inmediato si ya hay otro equivalente abierto para no abrir frentes duplicados.

**Why this priority**: Sin registro persistente no hay ciclo de vida ni auditoría.

**Independent Test**: Registrar dos reportes equivalentes devuelve `is_duplicate=true` en el segundo.

**Acceptance Scenarios**:

1. **Given** no hay incidentes registrados, **When** llega un reporte de caída de la pasarela de pagos sin identificador ni fecha, **Then** se registra con `201`, un identificador `INC-<HEX8>`, estado `OPEN`, su clasificación completa, `is_duplicate=false` y `duplicate_of=[]`.
2. **Given** una caída 502 de la pasarela de pagos ya resuelta y otra todavía abierta (`INC-1001`), **When** llega un nuevo reporte equivalente, **Then** se registra con `201`, `is_duplicate=true` y `duplicate_of=["INC-1001"]`, ignorando el incidente resuelto.

### User Story 2 - Auditar el SLA en cualquier instante (Priority: P1)

Operaciones audita cuánto SLA lleva consumido un incidente en un instante de referencia dado.

**Independent Test**: Un P2 registrado viernes tarde y consultado lunes temprano solo consume minutos hábiles.

**Acceptance Scenarios**:

1. **Given** un incidente P2 registrado el viernes `2026-11-06T17:00:00`, **When** se audita su SLA el lunes `2026-11-09T09:00:00`, **Then** obtiene `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.
2. **Given** un identificador inexistente, **When** se audita su SLA, **Then** recibe `404 Not Found`; **and given** un incidente registrado el lunes a las 10:00, **when** se audita con referencia 09:00 del mismo día, **then** recibe `422 Unprocessable Entity`.

### User Story 3 - Operación equivalente por CLI (Priority: P2)

Soporte registra y audita desde la terminal.

**Acceptance Scenarios**:

1. **Given** la base configurada, **When** soporte ejecuta `create` dos veces con reportes equivalentes y luego `sla --incident-id ... --reference-time ...`, **Then** obtiene los mismos contratos JSON que la API (`duplicate_of` en el segundo registro y `elapsed_minutes=120` en la auditoría), código `0`, y código `1` ante un identificador inexistente o un título vacío.

### Edge Cases

- Registro con estado `RESOLVED`: se guarda con fecha de resolución igual a la de creación y nunca cuenta como duplicado abierto.
- Referencia anterior a la creación en un incidente resuelto: se audita contra su resolución.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST registrar incidentes con `title` y `raw_text` obligatorios y `incident_id`, `created_at`, `status` opcionales.
- **FR-002**: El sistema MUST clasificar el reporte con el motor de triaje del dominio y persistir severidad, componente, equipo y clave de duplicados.
- **FR-003**: El sistema MUST informar `is_duplicate` y `duplicate_of` según el criterio de "equivalente abierto" clarificado.
- **FR-004**: El sistema MUST auditar el SLA con `reference_time` opcional, `404` si no existe y `422` si la referencia es anterior a la creación.
- **FR-005**: API y CLI MUST ofrecer la misma operación y el mismo contrato.

### Key Entities

- **Incidente registrado**: identificador, título, componente, severidad, estado, fecha de creación/resolución, equipo recomendado y clave de duplicados.
- **Evaluación de SLA**: minutos consumidos, permitidos, restantes, incumplimiento y escalamiento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los 5 escenarios pasan como pruebas automatizadas sobre almacenamiento aislado.
- **SC-002**: Ningún incidente `RESOLVED` aparece jamás en `duplicate_of`.

## Assumptions

- El estado de un incidente solo cambia al re-registrarlo (no hay endpoint de transición en este hito).
- Sin festivos en el horario hábil.
