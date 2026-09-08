"""
Etapa 2: Análisis del contenido de cada panel mediante IA.

Sistema modular: cualquier "proveedor" de visión implementa:

    analyze_panel_image(image_path: str, panel_label: str, panel_index: int, total_panels: int) -> dict

y devuelve un diccionario con las claves:
    description, characters, actions, emotions, dialogue, important_details

La IA debe indicar explícitamente cuando no puede determinar algo
(no inventar información).
"""
import os
from typing import Optional

# Claves estandarizadas del resultado del análisis
ANALYSIS_KEYS = (
    "description",
    "characters",
    "actions",
    "emotions",
    "dialogue",
    "important_details",
)

# Nivel de certeza para cada clave: "seen" (se ve claramente),
# "written" (aparece escrito), "inferred" (inferido razonablemente)
CERTAINTY_KEYS = ("seen", "written", "inferred")


def empty_analysis() -> dict:
    """Estructura vacía/limpia de un análisis de panel."""
    return {
        "description": "",
        "characters": [],
        "actions": [],
        "emotions": [],
        "dialogue": "",
        "important_details": "",
        "confidence": {},   # {"seen": [...], "written": [...], "inferred": [...]}
    }


# Prompt compartido por todos los proveedores. Refuerza: no inventar,
# diferenciar entre lo visible / lo escrito / lo inferido.
PROMPT_TEMPLATE = """Analiza esta viñeta de un cómic o manga. Es la viñeta {panel_index} de {total_panels} ({panel_label}).

Devuelve EXCLUSIVAMENTE un objeto JSON válido con estas claves:

{{
  "description": "descripción breve y objetiva de lo que ocurre en la escena",
  "characters": ["lista de personajes presentes; usa descripciones neutras si no se sabe el nombre, p.ej. 'hombre de pelo largo'"],
  "actions": ["acciones concretas que realizan los personajes"],
  "emotions": ["expresiones o emociones importantes observables"],
  "dialogue": "texto de los globos de diálogo, exactamente como aparece escrito; cadena vacía si no hay texto",
  "important_details": "detalles relevantes para entender la escena (objetos, cartel, ambiente, onomatopeyas...)",
  "confidence": {{
     "seen": ["claves sobre las que hay certeza visual clara"],
     "written": ["claves basadas únicamente en texto escrito en la viñeta"],
     "inferred": ["claves que son inferencias razonables, no seguras"]
  }}
}}

REGLAS IMPORTANTES:
- NO inventes información. Si algo no puede determinarse claramente, indícalo
  con frases como "no se puede determinar" en lugar de adivinar.
- Diferencia entre lo que se VE claramente, lo que aparece ESCRITO y lo que se
  puede INFERIR razonablemente (usa "confidence").
- "dialogue" debe ser solo texto literal de la viñeta.
- Responde en el mismo idioma en que esté escrito el cómic si es posible;
  si no, en español.
"""


PROMPT_SUMMARY = """A partir de los siguientes análisis ordenados de viñetas de un manga, escribe un guion de video resumen en español. Devuelve EXCLUSIVAMENTE un objeto JSON válido:\n\n{{\n  "synopsis": "sinopsis global de la historia en 3-5 frases, lista para ser narrada en el video",\n  "panels": ["frase corta que resume cada viñeta, EN EL MISMO ORDEN en que se listan, lista para mostrarse como subtítulo de su diapositiva"]\n}}\n\nSi algún dato es incierto, no lo inventes.\n\nANÁLISIS DE LAS VIÑETAS EN ORDEN DE LECTURA:\n{panels_text}\n"""

# Alias con nombre más descriptivo usado por summarize_story()
SUMMARY_PROMPT = PROMPT_SUMMARY


# --------------------------------------------------------------------------
# Proveedor: OpenAI (GPT-4o / GPT-4o-mini con visión)
# --------------------------------------------------------------------------
class OpenAIProvider:
    """Proveedor de visión usando la API de OpenAI.

    Variables de entorno:
        OPENAI_API_KEY      -> clave de API (obligatoria)
        OPENAI_VISION_MODEL -> modelo a usar (por defecto 'gpt-4o-mini')
    """

    name = "openai"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Falta OPENAI_API_KEY en el entorno para usar el proveedor OpenAI."
            )

    def analyze_panel_image(self, image_path: str, panel_label: str,
                            panel_index: int, total_panels: int) -> dict:
        import base64
        import json as _json
        from openai import OpenAI  # pip install openai

        with open(image_path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")

        client = OpenAI(api_key=self.api_key)
        prompt = PROMPT_TEMPLATE.format(
            panel_index=panel_index, total_panels=total_panels, panel_label=panel_label
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1200,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json_loose(raw)

    def summarize_story(self, panels_text: str) -> str:
        """Resumen narrativo (solo texto) a partir de los análisis de paneles."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(panels_text=panels_text)}
            ],
            max_tokens=800,
        )
        return (response.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------
# Proveedor: Google Gemini
# --------------------------------------------------------------------------
class GeminiProvider:
    """Proveedor de visión usando la API de Google Gemini.

    Variables de entorno:
        GEMINI_API_KEY       -> clave de API (obligatoria)
        GEMINI_VISION_MODEL  -> modelo (por defecto 'gemini-2.0-flash')
    """

    name = "gemini"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.environ.get("GEMINI_VISION_MODEL", "gemini-3.6-flash")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Falta GEMINI_API_KEY en el entorno para usar el proveedor Gemini."
            )

    def analyze_panel_image(self, image_path: str, panel_label: str,
                            panel_index: int, total_panels: int) -> dict:
        import google.generativeai as genai  # pip install google-generativeai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)

        with open(image_path, "rb") as fh:
            image_data = fh.read()

        prompt = PROMPT_TEMPLATE.format(
            panel_index=panel_index, total_panels=total_panels, panel_label=panel_label
        )
        result = model.generate_content(
            [prompt, {"mime_type": "image/png", "data": image_data}]
        )
        return _parse_json_loose(result.text or "")

    def summarize_story(self, panels_text: str) -> str:
        """Resumen narrativo (solo texto) a partir de los análisis de paneles."""
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        result = model.generate_content(SUMMARY_PROMPT.format(panels_text=panels_text))
        return (result.text or "").strip()


# --------------------------------------------------------------------------
# Proveedor de respaldo: sin IA (placeholder)
# --------------------------------------------------------------------------
class NoOpProvider:
    """Proveedor de prueba: no llama a ninguna API. Devuelve estructura vacía
    marcada como no analizada. Útil para probar la interfaz sin gastar cuota."""

    name = "noop"

    def analyze_panel_image(self, image_path: str, panel_label: str,
                            panel_index: int, total_panels: int) -> dict:
        return {
            "description": "(sin análisis: proveedor IA no configurado)",
            "characters": [],
            "actions": [],
            "emotions": [],
            "dialogue": "",
            "important_details": "",
            "confidence": {"seen": [], "written": [], "inferred": []},
        }


# Registro de proveedores disponibles: añadir aquí nuevos proveedores.
PROVIDERS = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "noop": NoOpProvider,
}


def get_provider(name: Optional[str] = None):
    """Fábrica: devuelve una instancia del proveedor indicado (o autodetectado
    según las variables de entorno disponibles)."""
    name = (name or "").strip().lower()
    if not name:
        if os.environ.get("OPENAI_API_KEY"):
            name = "openai"
        elif os.environ.get("GEMINI_API_KEY"):
            name = "gemini"
        else:
            name = "noop"
    if name not in PROVIDERS:
        raise ValueError(
            f"Proveedor de IA desconocido: '{name}'. Disponibles: {', '.join(PROVIDERS)}"
        )
    return PROVIDERS[name]()


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _parse_json_loose(raw: str) -> dict:
    """Extrae el primer objeto JSON de la respuesta del modelo, tolerando
    fences de markdown y texto alrededor. Devuelve {} si no hay JSON."""
    import json
    import re

    text = raw.strip()
    # quitar fences ```json ... ```
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # último recurso: primer bloque entre llaves
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}

    if not isinstance(data, dict):
        return {}

    base = empty_analysis()
    for key in ANALYSIS_KEYS:
        if key in data:
            base[key] = data[key]
    conf = data.get("confidence")
    if isinstance(conf, dict):
        base["confidence"] = {
            k: list(conf.get(k, [])) for k in CERTAINTY_KEYS if isinstance(conf.get(k), list)
        }
    # normalizar listas
    for key in ("characters", "actions", "emotions"):
        if isinstance(base[key], str):
            base[key] = [base[key]]
        base[key] = [str(x) for x in (base[key] or [])]
    for key in ("description", "dialogue", "important_details"):
        if base[key] is None:
            base[key] = ""
        else:
            base[key] = str(base[key])
    return base
