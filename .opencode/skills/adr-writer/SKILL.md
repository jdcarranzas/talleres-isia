---
name: adr-writer
description: Redacta o revisa Architecture Decision Records en docs/adr/ con el formato MADR estricto de IncidentOps. Úsala cuando haya que registrar una decisión estructural y difícil de revertir (motor de BD, topología de despliegue, estilo arquitectónico, nueva dependencia de infraestructura) o antes de enmendar la Constitución.
---

# ADR Writer (MADR estricto)

## Cuándo sí y cuándo no

- **Sí**: decisiones estructurales y costosas de revertir que cambian fronteras, motores, runtime o dependencias de infraestructura.
- **No**: detalles tácticos (nombres de endpoints, campos, tareas, archivos a tocar). Eso va en `spec.md` / `plan.md` / `tasks.md`.

## Procedimiento

1. Lee `docs/adr/000-template.md`, los ADRs existentes en `docs/adr/` y `.specify/memory/constitution.md`.
2. Toma el siguiente número libre: `docs/adr/NNN-titulo-en-kebab-case.md`.
3. Copia **exactamente** la estructura de la plantilla:
   - Metadatos: `Estado`, `Fecha` (YYYY-MM-DD), `Autor(es)`, `Reemplaza a` (y en el ADR antiguo solo se actualiza su línea `Estado` a "Reemplazado (parcial/total) por ADR-NNN").
   - Secciones: `1. Contexto y Problema`, `2. Opciones Consideradas`, `3. Decisión Arquitectónica`, `4. Consecuencias y Trade-offs`.
4. **Una sola decisión por archivo.** Si aparecen dos, crea dos ADRs.
5. **Mínimo 2 opciones reales**, cada una con ventajas y desventajas auténticas; no incluyas opciones de relleno ni *strawmen* que nadie elegiría.
6. La decisión explica el **por qué** en relación con las restricciones del contexto.
7. Diagrama **Mermaid opcional y solo estructural** (capas, fronteras, topología de contenedores). Nunca flujos `if/else` ni secuencias algorítmicas.
8. Consecuencias con **trade-offs negativos honestos** (costos, riesgos, deuda asumida).

## Prohibido

- Sección `Componentes Afectados`, rutas a archivos concretos como lista o viñetas de `Verificación`/comandos.
- Duplicar escenarios BDD o requisitos funcionales de `spec.md`, o listas de tareas/archivos de `plan.md`.
- Reescribir o borrar un ADR aceptado (registro *append-only*): si la decisión cambia, se emite un ADR nuevo que lo reemplaza.

## Después de aceptar el ADR

Orden causal: **ADR → `/speckit.constitution` (actualiza `.specify/memory/constitution.md` y su versión) → `/speckit.specify` del hito**.
