---
name: bdd-acceptance
description: Redacta escenarios BDD Given/When/Then en lenguaje de negocio para spec.md y los traduce 1:1 a pruebas pytest test_bdd_* con TestClient (FastAPI) y CliRunner (Typer). Úsala al ejecutar /speckit.specify o /speckit.clarify, al escribir o revisar tests/test_spec_*.py o cuando un escenario no tenga prueba.
---

# BDD de aceptación en IncidentOps

## 1. Escribir escenarios en `spec.md` (estilo Dan North)

- Formato: `**Given** <contexto de negocio>, **When** <acción del actor>, **Then** <resultado observable>`.
- Vocabulario ubicuo: incidente, reporte, severidad P0–P3, SLA, horario hábil, escalamiento, duplicado abierto, componente, equipo, soporte, Operaciones, Plataforma.
- **Prohibido** filtrar implementación: nada de nombres de clases o funciones Python, tablas o columnas SQL, librerías ni archivos. Sí se permiten contratos observables ya acordados (ruta HTTP, código de estado, campos JSON, nombre del subcomando CLI, código de salida).
- Un escenario = un comportamiento; valores concretos y deterministas (fechas ISO fijas, textos de reporte reales), nunca "ahora".
- Cubre siempre: camino feliz, caso borde/vacío, error de validación y paridad CLI.

## 2. Traducir a pruebas (`tests/test_spec_<NNN>_<tema>.py`)

- Una función `test_bdd_s<N>_<descripcion_en_snake_case>` por escenario, en el mismo orden del `spec.md`; los sub-casos usan sufijo (`s4b`) o `pytest.mark.parametrize`.
- Cuerpo con comentarios `# Given`, `# When`, `# Then` que repiten el texto del escenario.
- API: fixture `client` (`fastapi.testclient.TestClient(create_app(service))`) sobre `SQLiteIncidentRepository(":memory:")` y reloj fijo inyectado en `IncidentService`.
- CLI: fixture `cli_runner` (`typer.testing.CliRunner`) + fixture `cli_database` que apunta `DATABASE_URL` a un SQLite en `tmp_path`; verifica `exit_code` y `json.loads(result.stdout)`.
- Aislamiento total: sin red, sin Docker, sin dependencia del orden de ejecución. Integraciones con motores reales van marcadas con `skipif` por variable de entorno.
- Asierta el contrato completo cuando sea corto (`== {...}`) para detectar campos sobrantes o faltantes.

## 3. Cierre

`uv run pytest -v` debe mostrar cada `test_bdd_*` en `PASSED`. Si un escenario del `spec.md` no tiene prueba (o viceversa), repórtalo antes de dar el hito por terminado.
