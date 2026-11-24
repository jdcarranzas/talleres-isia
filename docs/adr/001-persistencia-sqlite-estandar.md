# ADR-001: Persistencia en SQLite con la biblioteca estándar `sqlite3`

- **Estado**: Aceptado — Reemplazado parcialmente por ADR-004 (restricción "solo `sqlite3`")
- **Fecha**: 2026-11-14
- **Autor(es)**: Equipo IncidentOps
- **Reemplaza a**: —

> Registro retroactivo: formaliza la decisión de persistencia vigente desde la Semana 1, sobre la que se apoyan la Constitución y el ADR-004. Se redacta en formato MADR estricto para mantener una sola convención en `docs/adr/`.

---

## 1. Contexto y Problema

IncidentOps necesita persistir incidentes y políticas de SLA para construir resúmenes operativos. El proyecto semilla es académico, se ejecuta en portátiles Windows/Linux/macOS sin servicios auxiliares y prioriza la reproducibilidad: cualquier dependencia de infraestructura (servidor de BD, ORM, migraciones) eleva el costo de arranque y oculta el SQL que se quiere optimizar (consultas N+1, índices compuestos).

---

## 2. Opciones Consideradas

1. **Opción A — SQLite embebido con `sqlite3` de la biblioteca estándar y SQL explícito**:
   - *Ventajas*: Cero dependencias y cero procesos externos; base en memoria para pruebas deterministas; el SQL (JOIN, índices) queda visible y auditable.
   - *Desventajas*: Un solo escritor; sin red ni alta disponibilidad; no apto como base dedicada de producción.
2. **Opción B — ORM (SQLAlchemy) sobre un servidor relacional desde el inicio**:
   - *Ventajas*: Portabilidad entre motores y migraciones gestionadas.
   - *Desventajas*: Exige un servidor para desarrollar y probar; abstrae el SQL que se busca optimizar; añade una dependencia pesada antes de tener una necesidad real de producción.

---

## 3. Decisión Arquitectónica

Se elige la **Opción A**: persistencia en SQLite mediante `sqlite3` estándar, con SQL parametrizado escrito a mano y sin ORMs. Cualquier cambio de motor exigirá un ADR específico.

---

## 4. Consecuencias y Trade-offs

- **Positivas**: Entorno reproducible con `uv sync`; pruebas rápidas sobre `:memory:`; el rendimiento se razona directamente sobre el SQL y los índices.
- **Negativas / Trade-offs**: Sin concurrencia de escritura ni despliegue multi-nodo; un futuro motor de producción requerirá un adaptador adicional y paridad de tipos (fechas) entre motores.
