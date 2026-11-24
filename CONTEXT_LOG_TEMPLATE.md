# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: `Juan David Carranza Sánchez`  
**Fecha**: `2026-11-14`  
**Modelos / Asistentes Utilizados**: `[Claude Haiku 5.5, Claude Opus 5.5]`

---

## 1. De Prompts Pobres a Técnicas Clásicas de *Prompt Engineering* (Reto 1: `src/triage_rules.py`)

### 1.1 Diagnóstico de un Prompt Pobre y Ambiguo
Analiza el siguiente prompt deficiente para el Reto 1:
> *"El archivo `triage_rules.py` funciona mal con algunos tickets del JSON. Agrégale el equipo recomendado y una clave para duplicados, y no pongas P0 cuando no sea urgente."*

Documenta al menos **3 modos de fallo o ambigüedades** de este prompt (p. ej., ausencia de contexto de dominio, restricciones negativas difusas, falta de enumeración de equipos válidos o ausencia de ejemplos canónicos):
1. `La instrucción del desarrollador junior no es explícita ni clara, resultando en un prompt vago que probablemente lleve muchas idas y venidas.`
2. `No hay suficiente contexto ni motivación, sólo una expresión vaga de negación`
3. `No existen ejemplos claros para aclarar ambigüedades que puedan llegar a existir`

### 1.2 Uso de *Self-Consistency*, *Chain-of-Thought* y *Few-Shot Prompting*
- ¿Cómo utilizaste *Chain-of-Thought* (`<analysis>`) y *Self-Consistency* (múltiples consultas independientes) para definir las reglas de clasificación de los casos ambiguos (`INC-1002`, `INC-1007`, `INC-1009`) y la agrupación de duplicados (`INC-1001`/`INC-1006` e `INC-1003`/`INC-1008`)?
* **Chain-of-Thought:** Se usó el análisis de cadena de pensamiento, donde se estructura el resultado por cada petición realizada y el modelo explica cada decisión tomada desde el resultado del clasificador y cómo hizo las reglas para clasificar de P0 a P3.
* **Self-Consistency:** Se plantearon diferentes sesiones con el prompt repetido y se obtuvieron los siguientes resultados 

| Iteración | Clasificación de casos ambiguos | Agrupación de duplicados |
| :--- | :---| :--- |
| Haiku 5.5, esfuerzo bajo | INC-1002: P1 <br> INC-1007: P0 <br> INC-1009: P2 | INC-1001 + INC-1006 gateway de pagos <br> INC-1003 + INC-1008 lentitud en historial| 
| Haiku 5.5, esfuerzo medio | INC-1002: P1 <br> INC-1007: P0 <br> INC-1009: P2 | INC-1001 + INC-1006 gateway de pagos <br> INC-1003 + INC-1008 relacionados pero no duplicados |
| Haiku 5.5, esfuerzo alto | INC-1002: P2 <br> INC-1007: P0 <br> INC-1009: P2 | INC-1001 + INC-1006 gateway de pagos <br> INC-1003 + INC-1008 Comparten misma causa probable |


- Copia el prompt mejorado que empleaste aplicando las técnicas clásicas (`<role>`, `<domain_rules>` con justificación del *porqué*, `<examples>` *Few-Shot* y `<task>`):

```xml
<role>
Actúa como Ingeniero Principal de Confiabilidad (SRE) y Seguridad en IncidentOps.
</role>
<context>
<lsp_context symbol="classify_incident_report">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:12
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:22
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:35
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:48
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje con IA."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    consistency_ratio: float = 1.0

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\triage_rules.py:27
def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente aplicando reglas heurísticas iniciales.

    DEUDA TÉCNICA INTENCIONAL:
    - Evalúa palabras sueltas ("hoy", "urgente") antes de analizar el impacto real
      (caída global vs. cuenta individual vs. entorno de staging).
    - No normaliza componentes ni identifica el equipo de guardia correspondiente.
    """
    text_lower = raw_text.lower()

    # Bug de diseño: si un usuario dice "necesito acceder hoy" por su cuenta bloqueada,
    # se dispara como P0 antes de verificar si es una caída global o un caso individual.
    if "urgente" in text_lower or "hoy" in text_lower or "502" in text_lower:
        severity: SeverityLevel = "P0"
    elif "94%" in text_lower or "timeout" in text_lower:
        severity = "P1"
    elif "lenta" in text_lower or "segundos" in text_lower:
        severity = "P2"
    else:
        severity = "P3"

    if "pago" in text_lower or "cobro" in text_lower or "tarjeta" in text_lower:
        component = "payments-gateway"
    elif "cuenta" in text_lower or "ingresar" in text_lower:
        component = "auth-identity"
    elif "postgresql" in text_lower or "conexiones" in text_lower:
        component = "database-cluster"
    elif "certificado" in text_lower or "tls" in text_lower:
        component = "infra-certificates"
    elif "botón" in text_lower or "color" in text_lower:
        component = "frontend-ui"
    else:
        component = "reporting-api"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=f"Clasificación heurística legacy asignada a {component} ({severity}).",
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\triage_rules.py:77
  L76:     for item in incidents:
  L77:         result = classify_incident_report(item["id"], item["raw_text"])
  L78:         snippet = item["raw_text"][:45] + "..." if len(item["raw_text"]) > 45 else item["raw_text"]
</lsp_context>
</context>
<domain_rules>
Debemos clasificar reportes de incidentes en cuatro niveles de severidad:
- P0 (SLA 60 min, guardia 24/7): Indisponibilidad global de un servicio crítico
(ej. pagos HTTP 502) o brecha activa de seguridad / fuga de datos entre
organizaciones (multi-tenant).
- P1 (SLA 240 min, guardia 24/7): Degradación severa de infraestructura compartida
con riesgo inminente de caída (ej. pool de conexiones de base de datos >90%).
- P2 (SLA 480 min, horario hábil L-V 08:00-18:00): Degradación moderada de
rendimiento sin caída del servicio (ej. reportes lentos >3s) o bloqueo operativo
que afecta únicamente a un usuario individual.
- P3 (SLA 1440 min, horario hábil): Solicitudes cosméticas de UI o tareas
preventivas de mantenimiento en entornos no productivos (staging).
Importante (Por qué): La prioridad depende del impacto real sobre la
disponibilidad, la integridad de datos multi-tenant y el radio de afectación, nunca
de palabras emocionales o de prisa subjetiva del usuario como "urgente" u "hoy".

Así mismo, se deben asignar los reportes de incidentes a los cuatro equipos disponibles: 
- Backend-Core: Funcionamiento principal
- Platform-SRE: Plataforma web 
- Data-DBA: Reportes e informes
- Security-IAM: Seguridad y manejo de permisos

De la misma forma, cada reporte de incidentes debe clasificar por medio de una clave 
normalizada tipo: <component>:<symptom_category> que permita identificar problemas
repetidos, por ejemplo, un error 502 en un punto específico o algo relacionado a la 
lentitud en la generación de reportes

</domain_rules>
<examples>
<example>
Input: "El botón de exportar tiene un gris muy claro, sería mejor azul."
<analysis>
1. Radio de afectación: Visual/cosmético, cero impacto funcional.
2. Riesgo de seguridad o caída: Ninguno.
</analysis>
<output>severity=P3 | component=frontend-ui | recommended_team=Platform-SRE | symptom_category=ui| </output>
</example>
<example>
Input: "No puedo entrar a mi correo corporativo desde mi celular, urge resolver
hoy."
<analysis>
1. Radio de afectación: Un único usuario (cuenta individual), el servicio global de
autenticación sigue operativo.
2. Nota léxica: Incluye la palabra "hoy", pero por regla de dominio la prisa
individual no eleva un ticket a guardia 24/7 (P0).
</analysis>
<output>severity=P2 | component=auth-identity | recommended_team = Security-IAM | symptom_category = auth|</output>
</example>
Input: "El sistema me pidió cambiar contraseña pero el plazo se venció 
y no tengo acceso y es requiero ayuda para acceder a mi correo."
<analysis>
1. Radio de afectación: Un único usuario (cuenta individual), el servicio global de
autenticación sigue operativo.
2. El usuario olvidó cambiar la contraseña, no arriesga la operación del negocio.
</analysis>
<output>severity=P2 | component=auth-identity | recommended_team = Security-IAM | symptom_category = auth|</output>
</example>
</examples>
<incidents>
[
  {
    "id": "INC-1001",
    "reporter": "carlos.mendoza@clientes-corp.com",
    "created_at": "2026-11-05T08:15:00",
    "raw_text": "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones con tarjeta de crédito desde hace 12 minutos. Ningún comercio puede cobrar."
  },
  {
    "id": "INC-1002",
    "reporter": "ana.gomez@clientes-corp.com",
    "created_at": "2026-11-05T09:10:00",
    "raw_text": "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. Necesito acceder hoy mismo porque debo enviar el informe de cierre a la junta directiva."
  },
  {
    "id": "INC-1003",
    "reporter": "soporte-nivel1@incidentops.internal",
    "created_at": "2026-11-05T10:05:00",
    "raw_text": "El dashboard de reportes históricos tarda cerca de 4.5 segundos en cargar cuando un cliente tiene más de 10,000 órdenes registradas. No da error, pero la experiencia es muy lenta."
  },
  {
    "id": "INC-1004",
    "reporter": "luis.torres@logistica-express.co",
    "created_at": "2026-11-05T11:20:00",
    "raw_text": "Sería excelente si pudieran cambiar el color del botón de exportar CSV a verde oscuro porque el gris actual casi no resalta en mi monitor secundario."
  },
  {
    "id": "INC-1005",
    "reporter": "alertas-monitoreo@incidentops.internal",
    "created_at": "2026-11-05T11:45:00",
    "raw_text": "El nodo primario de PostgreSQL muestra un uso de conexiones del 94% y timeouts intermitentes en el pool de conexiones del servicio de facturación."
  },
  {
    "id": "INC-1006",
    "reporter": "maria.rodriguez@retail-latam.com",
    "created_at": "2026-11-05T13:00:00",
    "raw_text": "Otra vez cayó la pasarela de cobros con tarjeta, a nuestros clientes les sale error 502 al intentar pagar el carrito de compras."
  },
  {
    "id": "INC-1007",
    "reporter": "auditoria@seguridad-fin.com",
    "created_at": "2026-11-05T14:30:00",
    "raw_text": "Detectamos que al cambiar el parámetro company_id en la URL del reporte PDF se pueden visualizar facturas pertenecientes a otra organización."
  },
  {
    "id": "INC-1008",
    "reporter": "pedro.sanchez@ventas-norte.com",
    "created_at": "2026-11-05T15:10:00",
    "raw_text": "El listado de planes e historial tarda más de 3 segundos en responder cada vez que abrimos la pestaña de clientes corporativos con más de 10,000 registros."
  },
  {
    "id": "INC-1009",
    "reporter": "elena.vargas@contabilidad-global.com",
    "created_at": "2026-11-05T16:40:00",
    "raw_text": "La exportación mensual a Excel se queda pensando unos 20 segundos pero al final sí descarga el archivo completo. Hoy tenemos cierre contable y nos preocupa que falle más tarde."
  },
  {
    "id": "INC-1010",
    "reporter": "devops-ci@incidentops.internal",
    "created_at": "2026-11-05T17:25:00",
    "raw_text": "El certificado TLS del entorno de staging vencerá en 14 días. Requiere rotación programada antes del próximo sprint."
  }
]
</incidents>
<task>
Usando los `<incidents>` de ejemplo, razona primero dentro de una
etiqueta `<analysis>` evaluando el radio de afectación, el impacto en
seguridad/disponibilidad y las trampas léxicas, para refactorizar 
src/triage_rules.py y src/models.py para que realicen la salida en el
formato de `<output>`. La salida que debes darme son los cambios que van en 
src/models.py y src/triage_rules.py para que finalmente agrupe los incidentes
duplicados mediante duplicate_group_key
</task>
```

---

## 2. Flujo Explorar $\rightarrow$ Destilar $\rightarrow$ Ejecutar en Contexto Limpio (Reto 2: Cálculo de SLA en Horario Hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Objetivo explorado**: Diseño del algoritmo de cálculo de SLA en horario hábil (`P2`/`P3`, Lunes–Viernes 08:00–18:00) vs. 24/7 (`P0`/`P1`) y regla de escalamiento preventivo al 75%.
- **Síntesis de tu exploración de alternativas y resumen destilado (máx. 10 líneas)**:
  > `[Decisión: intersectar ventanas por día, con costo O(n) en días. P0/P1 (24×7) conservan el cálculo actual en minutos de reloj. P2/P3 recorren cada día de inicio a fin, omiten sábados y domingos, y suman el solape con [08:00, 18:00) en hora local. Se acumulan segundos y se convierte a minutos una sola vez, al final. Se mantienen >= para escalar y > para incumplir. Descartadas: 4. Minutos de reloj para P2/P3 (código actual): genera falsos incumplimientos, por ejemplo 3720 min en lugar de 30. 5. Normalizar inicio y fin con casos especiales: la intersección ya cubre noches, fines de semana y el mismo día sin condicionales. 6. Fórmula O(1) por semanas completas: más propensa a errores; se aplaza salvo que el rendimiento lo exija. 7. Redondear a minutos por día: pierde hasta un minuto por cada día recorrido. 8. Festivos: fuera de alcance por ahora, aunque el diseño queda abierto a un conjunto de fechas inyectable. Pendiente: fijar la zona horaria de negocio con zoneinfo y actualizar el test de la línea 87.]`

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering*)
Copia el prompt estructurado con etiquetas XML que utilizaste en un nuevo chat limpio para generar el **ADR (`docs/adr/002-calculo-sla-horario-habil.md`)** y la refactorización de `src/sla_calculator.py`:

```xml
<context>
Estamos optimizando el módulo de consulta de incidentes de IncidentOps.
A continuación se incluye la definición actual de `get_active_incidents_summary`
extraída vía LSP y la plantilla oficial de ADR del equipo.
lsp_context: 
<lsp_context symbol="evaluate_sla_status">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:30
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:40
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:53
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:66
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: TeamName
    symptom_category: SymptomCategory
    impact_scope: ImpactScope
    rationale: str
    consistency_ratio: float = 1.0

    @property
    def duplicate_group_key(self) -> str:
        """Clave normalizada <component>:<symptom_category> para detectar recurrencias."""
        return f"{self.component}:{self.symptom_category}"

    def to_output_line(self) -> str:
        """Serializa el resultado en el formato <output> acordado."""
        return (
            f"severity={self.severity} | component={self.component} | "
            f"recommended_team={self.recommended_team} | "
            f"symptom_category={self.symptom_category} | "
            f"duplicate_group_key={self.duplicate_group_key}"
        )

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\sla_calculator.py:25
def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]

# [LSP textDocument/definition] src\sla_calculator.py:32
def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    # TODO(week-1-taller): Cuando rule.operates_24x7 es False (P2 y P3), solo deben
    # contabilizarse los minutos dentro del horario hábil (Lunes-Viernes 08:00-18:00).
    delta_seconds = (end_time - incident.created_at).total_seconds()
    elapsed_minutes = int(delta_seconds // 60)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED"
        and not is_breached
        and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\incident_repository.py:146
  L145:             )
  L146:             sla_eval = evaluate_sla_status(incident, reference_time=reference_time)
  L147:             results.append(

# [LSP textDocument/references] src\sla_calculator.py:87
  L86:     monday_morning = datetime(2026, 11, 9, 9, 0, 0)
  L87:     evaluation = evaluate_sla_status(sample_incident, reference_time=monday_morning)
  L88: 
</lsp_context>
Template: 
# ADR-000: [Título Corto de la Decisión Arquitectónica]

- **Estado**: Propuesto | Aceptado | Reemplazado
- **Fecha**: YYYY-MM-DD
- **Autor(es)**: [Nombre del Ingeniero / Equipo]
- **Componentes Afectados**: [`src/...`]

---

## 1. Contexto y Problema

Describe el problema técnico o de negocio actual, las limitaciones del código existente (por ejemplo, latencia, consultas N+1, errores de cálculo de SLA o limitaciones de escalabilidad) y las restricciones del sistema (p. ej., mantener cero dependencias externas, seguridad contra inyección SQL, determinismo).

---

## 2. Opciones Consideradas

1. **Opción A — [Nombre de la opción]**:
   - *Ventajas*: ...
   - *Desventajas*: ...
2. **Opción B — [Nombre de la opción]**:
   - *Ventajas*: ...
   - *Desventajas*: ...
3. **Opción C — [Nombre de la opción]**:
   - *Ventajas*: ...
   - *Desventajas*: ...

---

## 3. Decisión Arquitectónica

Explica claramente cuál opción fue elegida y **por qué**. Incluye un diagrama **Mermaid** (`flowchart TD`, `flowchart LR`, `sequenceDiagram` o `stateDiagram-v2`) que ilustre el diseño aprobado.

```mermaid
flowchart LR
    A["Solicitud / Evento"] --> B["Componente Refactorizado"]
    B --> C["Resultado Validado"]
```

---

## 4. Consecuencias e Impacto

- **Positivas**: Mejoras en rendimiento, mantenibilidad, precisión o consumo de recursos.
- **Negativas / Trade-offs**: Complejidad adicional asumida o límites conocidos de la solución.
- **Verificación**: Cómo se comprobará empíricamente que la implementación cumple esta decisión.

</context>
<decision_summary>
Decisión: intersectar ventanas por día, con costo O(n) en días.

P0/P1 (24×7) conservan el cálculo actual en minutos de reloj.
P2/P3 recorren cada día de inicio a fin, omiten sábados y domingos, y suman el solape con [08:00, 18:00) en hora local.
Se acumulan segundos y se convierte a minutos una sola vez, al final. Se mantienen >= para escalar y > para incumplir.

Descartadas:
4. Minutos de reloj para P2/P3 (código actual): genera falsos incumplimientos, por ejemplo 3720 min en lugar de 30.
5. Normalizar inicio y fin con casos especiales: la intersección ya cubre noches, fines de semana y el mismo día sin condicionales.
6. Fórmula O(1) por semanas completas: más propensa a errores; se aplaza salvo que el rendimiento lo exija.
7. Redondear a minutos por día: pierde hasta un minuto por cada día recorrido.
8. Festivos: fuera de alcance por ahora, aunque el diseño queda abierto a un conjunto de fechas inyectable.

Pendiente: fijar la zona horaria de negocio con zoneinfo y actualizar el test de la línea 87.
</decision_summary>
<task>
Redacta el documento `docs/adr/002-calculo-sla-horario-habil.md` siguiendo
las secciones de la plantilla e incluye un diagrama Mermaid (`stateDiagram-v2`
o `flowchart TD`)  que explique el cálculo y la transición a escalamiento. Te recibo el markdown para yo crear el documento.
</task>
```

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
Compara el comportamiento que observaste al interactuar con:
1. **Modelo Rápido / Estándar (ej. Flash, Mini, Haiku o modo estándar)**:
2. **Modelo de Razonamiento Extendido (*Thinking Model*)**:
- ¿En cuál de las tareas de la semana fue indispensable el modelo de razonamiento y en cuál bastó el modelo rápido?
- Usando Haiku se hicieron las pruebas de "fogueo" donde se testeaba el zero-shot, el chain-of-thought y self-consistency. En esos puntos Haiku incluso tenía algunos problemas. Opus 5.5 en medio fue suficiente para hacer el trabajo pesado como la implementación de la refactorización + la creación del adr con las decisiones tomadas y el traceback del proyecto. 


### 3.2 Matriz de Decisión Arquitectónica
Para la plataforma *IncidentOps* y su evolución futura, justifica qué paradigma es el adecuado en cada escenario:

| Escenario / Requerimiento | Paradigma Elegido (Código Determinista / ML Clásico / Asistente GenAI en Chat / LLM en Tiempo de Ejecución) | Justificación Técnica (Determinismo, Costo, Latencia, Riesgo de Alucinación) |
| :--- | :--- | :--- |
| 1. Contabilizar minutos hábiles transcurridos y verificar si un ticket superó el 75% de su SLA | Código determinista | Debido a que el requerimiento exigía cierto nivel de comprensión profunda, el problema real era pensar en diversos casos límite e implementarlos como regla para asegurar la consistencia del sistema. |
| 2. Explorar casos borde y redactar un ADR antes de modificar la arquitectura de consultas SQL | Asistente GenAI en Chat | Sí bien un(a) ingeniero(a) puede tener mucha experiencia, lo cierto es que la ayuda de un asistente de IA es invaluable para poder imaginar muchos más casos que el ingeniero(a) por sí solo puede pensar en un límite dado de tiempo|
| 3. Detectar anomalías numéricas en millones de métricas de CPU/RAM por minuto | ML Clásico | Una implementación de series temporales, encontrar divergencias en distribuciones, comparar percentiles y analizar grandes volúmenes de datos es la capacidad por excelencia del ML Clásico, con umbrales definidos o "reglas" estadísticas es posible detectar anomalías de manera eficiente y eficaz|
| 4. Clasificar reportes de incidentes redactados en lenguaje natural abierto cuando las reglas deterministas no cubren nuevos patrones | LLM en tiempo de ejecución | En estos casos, un agente de AI podría identificar y generar nuevos casos de uso para identificar reglas y nuevos escenarios que puedan surgir de la noche a la mañana |

---

## 4. Economía de Tokens y Curaduría de Contexto con `tiktoken` (LSP vs. `grep`/`read` vs. `glob`/`read`)

### 4.1 Medición Empírica en *IncidentOps*
Completa la tabla con los resultados obtenidos al auditar los símbolos con `uv run python -m src.context_audit --symbol evaluate_sla_status` (y `classify_incident_report`):

| Etapa |Estrategia de Recolección de Contexto | Alcance (Archivos / Nodos) | Caracteres Totales | Tokens (`tiktoken o200k_base`) | % de Reducción vs. Fuerza Bruta |
| :--- |:--- | :--- | :---: | :---: | :---: |
| evaluate_sla_status |**1. Fuerza Bruta (`glob` + `read` todo)** | Todos los archivos del proyecto | 62750 | 16548 | 0% (Línea base) |
| evaluate_sla_status |**2. Búsqueda Textual (`grep` + `read` `.py`)** | Archivos `.py` donde aparece el símbolo | 33643 | 8554 | 48.3% |
| evaluate_sla_status |**3. Semántica vía LSP (`definition` + `references` + `hover`)** | Solo definición, tipos asociados y líneas de invocación | 5445 | 1352 | 91.82% |

| Etapa |Estrategia de Recolección de Contexto | Alcance (Archivos / Nodos) | Caracteres Totales | Tokens (`tiktoken o200k_base`) | % de Reducción vs. Fuerza Bruta |
| :--- |:--- | :--- | :---: | :---: | :---: |
| classify_incident_report |**1. Fuerza Bruta (`glob` + `read` todo)** | Todos los archivos del proyecto | 62750 | 16548 | 0% (Línea base) |
| classify_incident_report |**2. Búsqueda Textual (`grep` + `read` `.py`)** | Archivos `.py` donde aparece el símbolo | 17087 | 4387 | 73.5% |
| classify_incident_report |**3. Semántica vía LSP (`definition` + `references` + `hover`)** | Solo definición, tipos asociados y líneas de invocación | 3728 | 955 | 94.22% |

### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Registra los tokens medidos con `tiktoken` para los 10 incidentes en JSON indentado, JSON compacto, YAML y CSV, y explica qué formato elegirías al inyectar datos tabulares o logs largos en la ventana de contexto.

Sí queremos hablar de ahorrar tokens, definitivamente el mejor formato es el CSV delimitado por "|", ya que es el que menos tokens cuesta, sin embargo, para la lectura, quizá un JSON compacto pueda ser más organizado no sólo para leerlo sino también para la comunicación con otros sistemas que no sean necesariamente un LLM
| Formato de Serialización | Caracteres | Tokens | 
| :--- | :---: | :---: |
JSON Indentado (indent=2)      | 2942         | 878 tokens
JSON Compacto (minified)       | 2641         | 728 tokens
YAML Equivalente               | 2579         | 755 tokens
CSV Delimitado por barra vertical         | 2171         | 617 tokens