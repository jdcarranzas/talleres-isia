# Feature Specification: Resumen de incidentes activos

**Feature Branch**: `002-active-incidents-summary`

**Created**: 2026-11-23

**Status**: Implemented

**Input**: User description: "Necesitamos consultar el resumen de incidentes actualmente activos (OPEN e IN_PROGRESS) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente."

## Clarifications

### Session 2026-11-23

- Q: ¿Qué interfaces expone el resumen? → A: `GET /api/v1/incidents/summary` con parámetro opcional `component`, y subcomando CLI `summary [--component ...] [--reference-time ...]`.
- Q: ¿Qué se devuelve si no hay incidentes activos o ninguno coincide con el componente? → A: `200 OK` / JSON válido con `total_active=0`, `breached_count=0` e `incidents=[]` (nunca 404).
- Q: ¿Contra qué instante se mide el SLA? → A: parámetro opcional `reference_time` (ISO 8601) para evaluaciones deterministas; por defecto, el instante actual.
- Q: ¿`ESCALATION_REQUIRED` cuenta como activo? → A: No en este hito; "activo" es exactamente `OPEN` e `IN_PROGRESS`, tal como lo pide Operaciones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver la carga activa y los incumplimientos (Priority: P1)

Operaciones necesita saber, desde el dashboard o la terminal, cuántos incidentes siguen en curso, cuántos ya incumplieron su SLA y el detalle de cada uno, para priorizar la atención.

**Why this priority**: Es la vista operativa mínima para decidir a quién escalar.

**Independent Test**: Con incidentes activos y resueltos registrados, una consulta devuelve solo los activos con su estado de SLA.

**Acceptance Scenarios**:

1. **Given** incidentes `OPEN` e `IN_PROGRESS` de varios componentes, uno de ellos con el SLA incumplido, y un incidente `RESOLVED`, **When** Operaciones consulta el resumen global en un instante de referencia, **Then** ve `total_active=3`, `breached_count=1` y el detalle (título, componente, severidad, estado, minutos transcurridos, incumplimiento y escalamiento) de cada activo, sin el resuelto.
2. **Given** el mismo tablero, **When** filtra por el componente `reporting-api`, **Then** solo ve los incidentes activos de ese componente con sus totales.
3. **Given** un componente sin incidentes activos, **When** consulta el resumen filtrado, **Then** recibe un resumen válido vacío (`total_active=0`, `breached_count=0`, `incidents=[]`).

### User Story 2 - Misma consulta desde la terminal (Priority: P2)

Soporte consulta el mismo resumen desde la CLI sin abrir el dashboard.

**Independent Test**: El subcomando `summary` devuelve el mismo contrato JSON que la API.

**Acceptance Scenarios**:

1. **Given** incidentes activos en la base configurada, **When** soporte ejecuta `summary --component payments-gateway --reference-time ...`, **Then** obtiene JSON equivalente al de la API y código de salida `0`.

### Edge Cases

- Incidente creado después del instante de referencia: cuenta como activo con `0` minutos consumidos.
- P2/P3 consultados en fin de semana: solo se cuentan minutos hábiles (ADR-002).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST listar únicamente incidentes en estado `OPEN` o `IN_PROGRESS`.
- **FR-002**: El sistema MUST informar `total_active`, `breached_count` y, por incidente, título, componente, severidad, estado, minutos transcurridos, si incumplió y si requiere escalamiento.
- **FR-003**: El sistema MUST permitir filtrar opcionalmente por componente.
- **FR-004**: El sistema MUST aceptar un `reference_time` opcional y usar el instante actual si se omite.
- **FR-005**: La API y la CLI MUST devolver el mismo contrato.

### Key Entities

- **Incidente activo**: incidente en curso con su severidad y su consumo de SLA en el instante de referencia.
- **Resumen**: agregado de los incidentes activos (totales + detalle).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los 4 escenarios pasan como pruebas automatizadas.
- **SC-002**: El resultado es idéntico para la misma base y el mismo `reference_time` (determinismo).

## Assumptions

- La política de SLA y el horario hábil son los de la Constitución (sin festivos).
- El orden del detalle es por fecha de creación ascendente.
