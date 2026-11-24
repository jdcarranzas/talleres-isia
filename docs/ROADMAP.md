# Roadmap de Producto y Operaciones — IncidentOps

| Hito | Nombre | Resultado de negocio esperado |
| :--- | :--- | :--- |
| **H001** | Triaje multi-interfaz | Clasificar y enrutar reportes de forma determinista, sin guardarlos, para consumo inmediato desde la web y la terminal. |
| **H002** | Resumen de incidentes activos | Consultar desde la web y la terminal cuántos incidentes siguen activos, cuántos incumplieron su SLA y filtrar por componente. |
| **H003** | Ciclo de vida, duplicados y SLA | Registrar los incidentes entrantes de forma persistente, avisar si ya existe otro equivalente abierto y auditar su SLA en cualquier instante. |
| **H004** | Persistencia relacional dedicada y runtime en contenedores | Ejecutar el servicio de forma reproducible en contenedores con una base de datos relacional dedicada y un chequeo real de conectividad. |

> El *cómo* (contratos, librerías, rutas) se decide en cada especificación, plan o ADR; este roadmap solo fija el *hacia dónde*.
