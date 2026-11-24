"""Triaje determinista de incidentes basado en impacto real, no en urgencia percibida.

Pipeline: normalizar -> componente -> síntoma -> radio de afectación
          -> severidad -> equipo -> duplicate_group_key.
Las palabras de prisa ("urgente", "hoy", ...) solo se registran como ignoradas.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

from src.domain.models import (
    SEVERITY_RANK,
    DuplicateGroup,
    ImpactScope,
    SeverityLevel,
    SymptomCategory,
    TeamName,
    TriageResult,
)

# --- Umbrales de dominio ----------------------------------------------------

LATENCY_THRESHOLD_SECONDS = 3.0
POOL_SATURATION_THRESHOLD = 90.0
CERT_CRITICAL_DAYS = 2

CRITICAL_COMPONENTS = frozenset({"payments-gateway", "auth-identity"})
UNCLASSIFIED_COMPONENT = "unclassified"

# --- Componentes (orden: más específico -> más genérico) --------------------

COMPONENT_RULES: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("payments-gateway", re.compile(
        r"pasarela|gateway de pagos|\bpag(o|os|ar)\b|\bcobr(o|os|ar)\b|tarjeta")),
    ("database-cluster", re.compile(
        r"postgres|mysql|pool de conexiones|uso de conexiones|base de datos")),
    ("infra-certificates", re.compile(r"certificado|\btls\b|\bssl\b")),
    ("auth-identity", re.compile(
        r"\bmi cuenta\b|cuenta bloqueada|contrasena|\bingresar\b|iniciar sesion|"
        r"\blogin\b|no tengo acceso")),
    ("frontend-ui", re.compile(r"\bboton\b|\bcolor\b|tipografia|\bicono\b|resalta")),
    ("reporting-api", re.compile(
        r"reporte|dashboard|informe|export|excel|\bcsv\b|listado|historial")),
)

COMPONENT_TEAM: Dict[str, TeamName] = {
    "payments-gateway": "Backend-Core",
    "auth-identity": "Security-IAM",
    "database-cluster": "Data-DBA",
    "reporting-api": "Data-DBA",
    "frontend-ui": "Platform-SRE",
    "infra-certificates": "Platform-SRE",
    UNCLASSIFIED_COMPONENT: "Platform-SRE",
}
SECURITY_SYMPTOMS = frozenset({"tenant_leak", "auth"})

# --- Síntomas ---------------------------------------------------------------

TENANT_LEAK_RE = re.compile(
    r"otras? organizacion(es)?|entre organizaciones|otro tenant|otra empresa|"
    r"otro cliente|fuga de datos|multi-?tenant|cross-?tenant")
HTTP_5XX_RE = re.compile(
    r"\b(http|error|codigo|status)\s*5\d{2}\b|bad gateway|service unavailable|"
    r"gateway timeout")
POOL_RE = re.compile(
    r"pool de conexiones|uso de conexiones|max_connections|too many connections")
CERT_EXPIRY_RE = re.compile(r"certificado.{0,60}(venc|expir|caduc)")
AUTH_RE = re.compile(
    r"bloquead|contrasena|no puedo (entrar|ingresar|acceder)|no tengo acceso|credenciales")
EXPORT_RE = re.compile(r"export|descarg")
LATENCY_RE = re.compile(r"\btarda|\blent[oa]s?\b|\bsegundos?\b|se queda pensando|demora")
UI_RE = re.compile(r"\bcolor\b|\bboton\b|resalta|tipografia|alineacion|\bicono\b")

# --- Radio de afectación ----------------------------------------------------

NON_PROD_RE = re.compile(r"\bstaging\b|\bsandbox\b|\bqa\b|entorno de (pruebas|desarrollo)")
GLOBAL_RE = re.compile(
    r"\btod[oa]s (las|los) (transacciones|usuarios|clientes|comercios|organizaciones|peticiones)|"
    r"\bningun[oa]? (comercio|cliente|usuario)|\bcayo\b|\bcaid[oa]\b|fuera de servicio")
INDIVIDUAL_RE = re.compile(
    r"\bmi (cuenta|correo|usuario|monitor|equipo|celular|perfil)\b|\bno puedo\b")

# --- Trampas léxicas (se registran, nunca elevan severidad) -----------------

URGENCY_RE = re.compile(
    r"\burgente\b|\burge\b|\bhoy\b|\bya mismo\b|\binmediat\w*|\basap\b|cuanto antes")

# --- Extractores numéricos --------------------------------------------------

PERCENT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
SECONDS_RE = re.compile(r"(mas de\s+)?(\d+(?:[.,]\d+)?)\s*segundos?")
DAYS_RE = re.compile(r"(\d+)\s*dias?\b")


def _normalize(raw_text: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados."""
    decomposed = unicodedata.normalize("NFKD", raw_text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip()


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _extract_percentage(text: str) -> Optional[float]:
    match = PERCENT_RE.search(text)
    return _to_float(match.group(1)) if match else None


def _extract_days(text: str) -> Optional[int]:
    match = DAYS_RE.search(text)
    return int(match.group(1)) if match else None


def _exceeds_latency_threshold(text: str) -> bool:
    match = SECONDS_RE.search(text)
    if match is None:
        return True  # lentitud reportada sin métrica: se asume degradación moderada
    value = _to_float(match.group(2))
    is_lower_bound = match.group(1) is not None  # "más de 3 segundos" => > 3
    return value > LATENCY_THRESHOLD_SECONDS or (
        is_lower_bound and value >= LATENCY_THRESHOLD_SECONDS
    )


def _detect_component(text: str) -> str:
    for component, pattern in COMPONENT_RULES:
        if pattern.search(text):
            return component
    return UNCLASSIFIED_COMPONENT


def _detect_symptom(text: str) -> SymptomCategory:
    # La seguridad multi-tenant se evalúa primero: nunca debe quedar enmascarada.
    if TENANT_LEAK_RE.search(text):
        return "tenant_leak"
    if HTTP_5XX_RE.search(text):
        return "http_5xx"
    if POOL_RE.search(text):
        return "connection_pool"
    if CERT_EXPIRY_RE.search(text):
        return "cert_expiry"
    if AUTH_RE.search(text):
        return "auth"
    if LATENCY_RE.search(text):
        return "export_latency" if EXPORT_RE.search(text) else "latency"
    if UI_RE.search(text):
        return "ui"
    return "other"


def _detect_scope(text: str) -> ImpactScope:
    if NON_PROD_RE.search(text):
        return "non_production"
    if GLOBAL_RE.search(text):
        return "global"
    if INDIVIDUAL_RE.search(text):
        return "individual"
    return "shared"


def _decide_severity(
    component: str, symptom: SymptomCategory, scope: ImpactScope, text: str
) -> Tuple[SeverityLevel, str]:
    """Matriz de severidad: (síntoma, radio de afectación, métricas) -> P0..P3."""
    if symptom == "tenant_leak":
        return "P0", "brecha de aislamiento multi-tenant (datos de otra organización expuestos)"
    if scope == "non_production":
        return "P3", "afecta únicamente un entorno no productivo"

    if symptom == "http_5xx":
        if scope == "global":
            if component in CRITICAL_COMPONENTS:
                return "P0", "indisponibilidad global de un servicio crítico"
            return "P1", "errores 5xx globales en un servicio no crítico"
        if scope == "individual":
            return "P2", "error 5xx reportado por un único usuario"
        return "P1", "errores 5xx parciales en un servicio compartido"

    if symptom == "connection_pool":
        usage = _extract_percentage(text)
        if usage is not None and usage >= POOL_SATURATION_THRESHOLD:
            return "P1", f"saturación del pool de conexiones ({usage:g}% >= {POOL_SATURATION_THRESHOLD:g}%)"
        return "P2", "presión moderada sobre el pool de conexiones"

    if symptom == "cert_expiry":
        days = _extract_days(text)
        if days is None or days <= CERT_CRITICAL_DAYS:
            return "P1", "certificado productivo vencido o por vencer de forma inminente"
        return "P2", f"certificado productivo vence en {days} días"

    if symptom == "auth":
        if scope == "global":
            return "P0", "caída global del servicio de autenticación"
        return "P2", "bloqueo operativo que afecta a un usuario individual"

    if symptom in ("latency", "export_latency"):
        if _exceeds_latency_threshold(text):
            return "P2", f"degradación moderada de rendimiento (> {LATENCY_THRESHOLD_SECONDS:g}s) sin caída"
        return "P3", "latencia dentro del umbral tolerado"

    if symptom == "ui":
        return "P3", "solicitud cosmética de UI sin impacto funcional"

    if scope == "individual":
        return "P2", "bloqueo individual sin síntoma reconocido; requiere revisión humana"
    return "P3", "sin señales de impacto reconocidas; requiere revisión humana"


HTTP_STATUS_CODE_RE = re.compile(r"\b(5\d{2})\b")


def _symptom_signature(symptom: SymptomCategory, text: str) -> Optional[str]:
    """Firma estable del síntoma para la clave de duplicados.

    Para errores 5xx se incluye el código HTTP concreto (``http-502-outage``) de modo
    que una caída 502 y una 504 del mismo componente no se agrupen como el mismo
    incidente. Para el resto de síntomas se usa la categoría tal cual.
    """
    if symptom != "http_5xx":
        return None
    match = HTTP_5XX_RE.search(text)
    code = HTTP_STATUS_CODE_RE.search(match.group(0)) if match else None
    return f"http-{code.group(1) if code else '5xx'}-outage"


def _route_team(component: str, symptom: SymptomCategory) -> TeamName:
    if symptom in SECURITY_SYMPTOMS:
        return "Security-IAM"
    return COMPONENT_TEAM.get(component, "Platform-SRE")


def _find_urgency_terms(text: str) -> List[str]:
    return sorted({m.group(0) for m in URGENCY_RE.finditer(text)})


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte por radio de afectación e impacto, ignorando urgencia subjetiva."""
    text = _normalize(raw_text)
    component = _detect_component(text)
    symptom = _detect_symptom(text)
    scope = _detect_scope(text)
    severity, reason = _decide_severity(component, symptom, scope, text)
    team = _route_team(component, symptom)

    rationale = f"{reason}; alcance={scope}"
    ignored = _find_urgency_terms(text)
    if ignored:
        rationale += f"; términos de urgencia ignorados: {', '.join(ignored)}"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        recommended_team=team,
        symptom_category=symptom,
        impact_scope=scope,
        rationale=rationale,
        symptom_signature=_symptom_signature(symptom, text),
    )


def group_duplicates(results: Iterable[TriageResult]) -> List[DuplicateGroup]:
    """Agrupa por duplicate_group_key; el grupo hereda la severidad más alta."""
    buckets: Dict[str, List[TriageResult]] = {}
    for result in results:
        buckets.setdefault(result.duplicate_group_key, []).append(result)

    groups: List[DuplicateGroup] = []
    for key, members in buckets.items():
        lead = min(members, key=lambda r: SEVERITY_RANK[r.severity])
        groups.append(
            DuplicateGroup(
                duplicate_group_key=key,
                incident_ids=tuple(m.incident_id for m in members),
                highest_severity=lead.severity,
                recommended_team=lead.recommended_team,
            )
        )
    return sorted(
        groups,
        key=lambda g: (SEVERITY_RANK[g.highest_severity], -g.occurrences, g.duplicate_group_key),
    )

def _snippet(raw_text: str, size: int = 45) -> str:
    return raw_text[:size] + "..." if len(raw_text) > size else raw_text

def run_triage(incidents: List[dict]) -> List[DuplicateGroup]:
    header = (
        f"{'ID':<10} | {'Sev.':<5} | {'Equipo':<13} | "
        f"{'duplicate_group_key':<34} | Extracto del Reporte"
    )
    separator = "-" * 125
    print(header)
    print(separator)

    results: List[TriageResult] = []
    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        results.append(result)
        print(
            f"{result.incident_id:<10} | {result.severity:<5} | "
            f"{result.recommended_team:<13} | {result.duplicate_group_key:<34} | "
            f"{_snippet(item['raw_text'])}"
        )
    print(separator)

    print("\nSalida en formato <output>:")
    for result in results:
        print(f"  {result.incident_id}: {result.to_output_line()}")

    groups = group_duplicates(results)
    print("\nGrupos por duplicate_group_key:")
    for group in groups:
        flag = "  [RECURRENTE]" if group.is_recurrent else ""
        print(
            f"  {group.duplicate_group_key:<34} {group.highest_severity:<3} "
            f"{group.recommended_team:<13} {', '.join(group.incident_ids)}{flag}"
        )
    return groups


SAMPLE_INCIDENTS: List[dict] = [
    {"id": "INC-1001", "raw_text": "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones con tarjeta de crédito desde hace 12 minutos. Ningún comercio puede cobrar."},
    {"id": "INC-1002", "raw_text": "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. Necesito acceder hoy mismo porque debo enviar el informe de cierre a la junta directiva."},
    {"id": "INC-1003", "raw_text": "El dashboard de reportes históricos tarda cerca de 4.5 segundos en cargar cuando un cliente tiene más de 10,000 órdenes registradas. No da error, pero la experiencia es muy lenta."},
    {"id": "INC-1004", "raw_text": "Sería excelente si pudieran cambiar el color del botón de exportar CSV a verde oscuro porque el gris actual casi no resalta en mi monitor secundario."},
    {"id": "INC-1005", "raw_text": "El nodo primario de PostgreSQL muestra un uso de conexiones del 94% y timeouts intermitentes en el pool de conexiones del servicio de facturación."},
    {"id": "INC-1006", "raw_text": "Otra vez cayó la pasarela de cobros con tarjeta, a nuestros clientes les sale error 502 al intentar pagar el carrito de compras."},
    {"id": "INC-1007", "raw_text": "Detectamos que al cambiar el parámetro company_id en la URL del reporte PDF se pueden visualizar facturas pertenecientes a otra organización."},
    {"id": "INC-1008", "raw_text": "El listado de planes e historial tarda más de 3 segundos en responder cada vez que abrimos la pestaña de clientes corporativos con más de 10,000 registros."},
    {"id": "INC-1009", "raw_text": "La exportación mensual a Excel se queda pensando unos 20 segundos pero al final sí descarga el archivo completo. Hoy tenemos cierre contable y nos preocupa que falle más tarde."},
    {"id": "INC-1010", "raw_text": "El certificado TLS del entorno de staging vencerá en 14 días. Requiere rotación programada antes del próximo sprint."},
]

if __name__ == "__main__":
    run_triage(SAMPLE_INCIDENTS)
