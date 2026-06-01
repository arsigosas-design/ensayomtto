"""
Agente simple con Claude usando tool use loop.
"""

import json
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

# --- Definición de herramientas ---

TOOLS = [
    {
        "name": "buscar_clima",
        "description": "Obtiene el clima actual de una ciudad.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ciudad": {"type": "string", "description": "Nombre de la ciudad"}
            },
            "required": ["ciudad"],
        },
    },
    {
        "name": "calcular",
        "description": "Evalúa una expresión matemática simple.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expresion": {
                    "type": "string",
                    "description": "Expresión matemática, ej: '2 + 2' o '10 * 5'",
                }
            },
            "required": ["expresion"],
        },
    },
]


# --- Implementación de herramientas ---

def buscar_clima(ciudad: str) -> str:
    # En producción: conectar a una API real (ej. OpenWeatherMap)
    climas_demo = {
        "madrid": "Soleado, 24°C",
        "bogota": "Parcialmente nublado, 18°C",
        "buenos aires": "Lluvioso, 15°C",
        "mexico": "Despejado, 28°C",
    }
    return climas_demo.get(ciudad.lower(), f"No se encontró información para '{ciudad}'")


def calcular(expresion: str) -> str:
    try:
        # Seguro solo para operaciones básicas
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expresion):
            return "Error: solo se permiten operaciones básicas (+, -, *, /)"
        resultado = eval(expresion)  # noqa: S307
        return str(resultado)
    except Exception as e:
        return f"Error al calcular: {e}"


def ejecutar_herramienta(nombre: str, parametros: dict) -> str:
    if nombre == "buscar_clima":
        return buscar_clima(**parametros)
    if nombre == "calcular":
        return calcular(**parametros)
    return f"Herramienta '{nombre}' no encontrada"


# --- Loop principal del agente ---

def run_agent(pregunta: str) -> str:
    messages = [{"role": "user", "content": pregunta}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        # Claude quiere usar una herramienta
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    resultado = ejecutar_herramienta(block.name, block.input)
                    print(f"  [herramienta] {block.name}({json.dumps(block.input)}) → {resultado}")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": resultado,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        # Claude terminó
        else:
            return next(
                block.text for block in response.content if hasattr(block, "text")
            )


# --- Punto de entrada ---

if __name__ == "__main__":
    preguntas = [
        "¿Qué clima hace hoy en Madrid y en Bogotá?",
        "¿Cuánto es 123 * 456?",
        "¿Cuánto es (50 + 30) * 2 y cómo está el clima en México?",
    ]

    for pregunta in preguntas:
        print(f"\nPregunta: {pregunta}")
        respuesta = run_agent(pregunta)
        print(f"Respuesta: {respuesta}")
        print("-" * 60)
