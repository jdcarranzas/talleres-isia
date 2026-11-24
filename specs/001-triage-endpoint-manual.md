# Spec 001 — Triaje multi-interfaz (SDD manual, Iteración 1)

- **Hito**: H001 (`docs/ROADMAP.md`) · **Estado**: Implementado · **Fecha**: 2026-11-23
- **Requerimiento crudo**: "Necesitamos exponer el motor de triaje como servicio HTTP para que el frontend lo consuma y también como comando CLI para que soporte pueda probar reportes rápido desde terminal."

## Decisiones acordadas en la elicitación (modo Plan)

| Pregunta | Decisión |
| :--- | :--- |
| ¿Se guarda el reporte? | No. Operación *stateless*: un único caso de uso compartido de triaje para HTTP y CLI. |
| Contrato HTTP | `POST /api/v1/incidents/triage` con `{"incident_id": str, "raw_text": str}` → `200 OK` con todos los campos del resultado de triaje (severidad, componente, equipo, categoría de síntoma, alcance, justificación, consistencia y clave de duplicados). |
| Entradas vacías | Cualquier campo vacío o con solo espacios → `422 Unprocessable Entity`. |
| Contrato CLI | `triage --incident-id ... --raw-text ...` imprime el mismo JSON por salida estándar (código `0`); entradas vacías → error y código `1`. |
| Clave de duplicados de caídas HTTP | `<componente>:http-<código>-outage` (p. ej. `payments-gateway:http-502-outage`) para no mezclar caídas con códigos distintos del mismo componente. |
| ¿La urgencia del texto ("urgente", "hoy") cambia la severidad? | No; solo queda registrada en la justificación (regla de la Constitución). |

## Escenarios BDD

### Escenario 1 — Caída crítica HTTP 502 en la pasarela de pagos
- **Given** un reporte que indica que la pasarela de pagos devuelve HTTP 502 en todas las transacciones y ningún comercio puede cobrar
- **When** el frontend lo envía al servicio de triaje
- **Then** recibe `200` con `severity="P0"`, `component="payments-gateway"`, `recommended_team="Backend-Core"` y `duplicate_group_key="payments-gateway:http-502-outage"`

### Escenario 2 — Cuenta individual bloqueada que menciona "hoy"
- **Given** un usuario cuya propia cuenta quedó bloqueada y que pide acceso "hoy mismo"
- **When** el reporte se envía al triaje
- **Then** recibe `200` con `severity="P2"` y `recommended_team="Security-IAM"`, sin falso positivo P0

### Escenario 3 — Entradas vacías o con solo espacios
- **Given** un reporte con `raw_text="   "` o con `incident_id=""`
- **When** se envía al triaje
- **Then** el servicio responde `422 Unprocessable Entity`

### Escenario 4 — Paridad en CLI
- **Given** el mismo reporte de caída 502 del Escenario 1
- **When** soporte ejecuta `triage --incident-id INC-1001 --raw-text "..."`
- **Then** obtiene JSON válido con `severity="P0"` y `recommended_team="Backend-Core"` y código de salida `0`

## Trazabilidad

`tests/test_spec_001_triage.py` (`test_bdd_s1` … `test_bdd_s4b`).

> Nota de la plenaria: el plan técnico y las tareas de esta iteración se acordaron en la conversación del modo Plan y **no** quedaron versionados; ver la comparación en `SDD_LOG.md` §2.
