"""
Agente de ventas - Sierra Urbanística
Redacta y envía correos comerciales personalizados a constructoras via Outlook.

Requisitos:
- pip install anthropic msal requests
- Crear app en Azure AD con permiso Mail.Send
- Configurar variables de entorno (ver .env.example)
"""

import json
import os
import anthropic
import msal
import requests

# --- Configuración ---

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

# Credenciales de Azure AD / Microsoft Graph
TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "camilo.arbelaez@outlook.com")

GRAPH_API = "https://graph.microsoft.com/v1.0"

# Información de Sierra Urbanística (extraída del brochure oficial)
PERFIL_EMPRESA = f"""
SIERRA URBANÍSTICA — Empresa colombiana con sede en Medellín, Antioquia.
Misión: "Tenemos la vocación de transformar territorios y construir oportunidades."
Web: www.sierraurbanistica.com

SERVICIOS PRINCIPALES:

1. Desarrollo de obras de urbanismo:
   - Ejecución de movimientos de tierra (descapote, excavación, llenos, compactación)
   - Aplicación de estructuras de pavimentos (vías vehiculares, peatonales, andenes)
   - Instalación de acueductos y alcantarillado
   - Instalación de redes de gas

2. Comercialización de materiales pétreos para construcción:
   - Bases granulares
   - Triturados
   - Arenas
   - Otros materiales pétreos en portafolio

DIFERENCIADORES:
- Calidad garantizada desde el origen
- Red logística eficiente para transporte y entrega de materiales con cobertura
  en todo el departamento de Antioquia
- Experiencia en construcción de proyectos urbanísticos sostenibles
- Compromiso con el desarrollo de los territorios
- Soluciones integrales, confiables y de alta calidad

ALIADOS ESTRATÉGICOS (respaldan nuestra capacidad):
- Cantera Santa Rita
- Asfaltos Medellín S.A.S
- Triturados Peñalisa S.A.
- Postequipos S.A.S (prefabricados de concreto)

CONTACTO:
- Correo: camilo.arbelaez@outlook.com
- Celular: 313 7374484
- Dirección: CR 43A # 19 A 87, Medellín
- Web: www.sierraurbanistica.com
"""


# --- Autenticación Microsoft Graph ---

def get_access_token() -> str:
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Error de autenticación: {result.get('error_description')}")
    return result["access_token"]


# --- Herramientas del agente ---

TOOLS = [
    {
        "name": "redactar_correo",
        "description": (
            "Redacta un correo comercial personalizado para una constructora, "
            "basado en el perfil de la empresa y los datos del destinatario."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_empresa": {"type": "string", "description": "Nombre de la constructora"},
                "nombre_contacto": {"type": "string", "description": "Nombre del contacto (opcional)"},
                "enfoque": {
                    "type": "string",
                    "description": "Servicio o necesidad específica a destacar (opcional)",
                },
            },
            "required": ["nombre_empresa"],
        },
    },
    {
        "name": "enviar_correo",
        "description": "Envía un correo electrónico via Outlook usando Microsoft Graph API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destinatario_email": {"type": "string", "description": "Email del destinatario"},
                "destinatario_nombre": {"type": "string", "description": "Nombre del destinatario"},
                "asunto": {"type": "string", "description": "Asunto del correo"},
                "cuerpo_html": {"type": "string", "description": "Cuerpo del correo en HTML"},
            },
            "required": ["destinatario_email", "asunto", "cuerpo_html"],
        },
    },
    {
        "name": "registrar_envio",
        "description": "Registra el resultado del envío en el log de campaña.",
        "input_schema": {
            "type": "object",
            "properties": {
                "empresa": {"type": "string"},
                "email": {"type": "string"},
                "estado": {"type": "string", "enum": ["enviado", "fallido", "omitido"]},
                "nota": {"type": "string", "description": "Observación adicional"},
            },
            "required": ["empresa", "email", "estado"],
        },
    },
]


# --- Implementación de herramientas ---

def redactar_correo(nombre_empresa: str, nombre_contacto: str = "", enfoque: str = "") -> str:
    """Usa Claude para redactar un correo personalizado."""
    saludo = f"Estimado equipo de {nombre_empresa}"
    if nombre_contacto:
        saludo = f"Estimado/a {nombre_contacto}"

    enfoque_extra = ""
    if enfoque:
        enfoque_extra = f"\nDestaca especialmente el servicio de: {enfoque}"

    prompt = f"""Redacta un correo comercial profesional y cálido de parte de Sierra Urbanística
para la constructora '{nombre_empresa}'.{enfoque_extra}

Perfil de Sierra Urbanística:
{PERFIL_EMPRESA}

El correo debe:
- Usar el saludo: "{saludo}"
- Ser conciso (máximo 4 párrafos)
- Mencionar 1-2 servicios relevantes para una constructora
- Incluir un llamado a la acción claro (agendar reunión o llamada)
- Formato HTML limpio (usa <p>, <strong>, <br>)
- Tono profesional pero cercano, en español

Devuelve SOLO el HTML del cuerpo del correo y el asunto en JSON:
{{"asunto": "...", "cuerpo_html": "..."}}"""

    resp = CLIENT.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def enviar_correo(
    destinatario_email: str,
    asunto: str,
    cuerpo_html: str,
    destinatario_nombre: str = "",
) -> str:
    """Envía correo via Microsoft Graph API."""
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        payload = {
            "message": {
                "subject": asunto,
                "body": {"contentType": "HTML", "content": cuerpo_html},
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": destinatario_email,
                            "name": destinatario_nombre or destinatario_email,
                        }
                    }
                ],
            },
            "saveToSentItems": True,
        }

        resp = requests.post(
            f"{GRAPH_API}/users/{SENDER_EMAIL}/sendMail",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code == 202:
            return "enviado"
        return f"error_{resp.status_code}: {resp.text}"

    except Exception as e:
        return f"excepcion: {e}"


_log_envios: list[dict] = []

def registrar_envio(empresa: str, email: str, estado: str, nota: str = "") -> str:
    _log_envios.append({"empresa": empresa, "email": email, "estado": estado, "nota": nota})
    return f"Registrado: {empresa} → {estado}"


def ejecutar_herramienta(nombre: str, params: dict) -> str:
    if nombre == "redactar_correo":
        return redactar_correo(**params)
    if nombre == "enviar_correo":
        return enviar_correo(**params)
    if nombre == "registrar_envio":
        return registrar_envio(**params)
    return f"Herramienta '{nombre}' no encontrada"


# --- Loop del agente ---

def run_agent(tarea: str) -> str:
    messages = [{"role": "user", "content": tarea}]

    system = f"""Eres el agente comercial de Sierra Urbanística.
Tu misión es redactar y enviar correos comerciales personalizados a constructoras.

Flujo para cada constructora:
1. Usa 'redactar_correo' para crear el correo personalizado
2. Parsea el JSON devuelto para obtener asunto y cuerpo_html
3. Usa 'enviar_correo' con los datos del destinatario
4. Usa 'registrar_envio' con el resultado

Perfil de la empresa:
{PERFIL_EMPRESA}"""

    while True:
        response = CLIENT.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    resultado = ejecutar_herramienta(block.name, block.input)
                    print(f"  [{block.name}] → {str(resultado)[:120]}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": resultado,
                    })
            messages.append({"role": "user", "content": results})
        else:
            return next(b.text for b in response.content if hasattr(b, "text"))


# --- Punto de entrada ---

if __name__ == "__main__":
    # Lista de constructoras destino
    constructoras = [
        {"empresa": "Constructora Bolívar", "email": "contacto@cbolvar.com", "contacto": "Gerencia Comercial"},
        {"empresa": "Coninsa Ramon H.", "email": "info@coninsa.co", "contacto": ""},
        {"empresa": "Constructora Nación", "email": "ventas@cnacion.com", "contacto": ""},
    ]

    tarea = f"""Ejecuta la campaña de correos comerciales de Sierra Urbanística.

Envía un correo personalizado a cada una de estas constructoras:
{json.dumps(constructoras, ensure_ascii=False, indent=2)}

Para cada una: redacta el correo, envíalo y registra el resultado."""

    print("Iniciando campaña de correos...\n")
    resumen = run_agent(tarea)
    print(f"\nResumen:\n{resumen}")

    if _log_envios:
        print("\nLog de envíos:")
        for entry in _log_envios:
            print(f"  ✓ {entry['empresa']} ({entry['email']}) → {entry['estado']}")
