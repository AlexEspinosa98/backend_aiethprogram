import base64
import json
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import get_settings

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ESPECIE_FALLBACK = {
    "nombre_comun": "Especie no identificada",
    "nombre_cientifico": "Desconocida",
    "nativa_colombia": None,
    "categoria_amenaza": "no aplica",
    "confianza": "baja",
}


class _EspecieIdentificada(BaseModel):
    nombre_comun: str = Field(description="Nombre común de la especie identificada")
    nombre_cientifico: str = Field(description="Nombre científico de la especie")
    nativa_colombia: bool = Field(description="Si la especie es nativa de Colombia")
    categoria_amenaza: str = Field(
        description='Categoría de amenaza de referencia: "CR", "EN", "VU" o "no aplica"'
    )
    confianza: str = Field(
        description='Nivel de confianza de la identificación: "alta", "media" o "baja"'
    )


def _modelo() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key)


def _especies_referencia() -> list[dict]:
    with open(_DATA_DIR / "especies_amenazadas_colombia.json", encoding="utf-8") as f:
        return json.load(f)


def _foto_a_data_url(foto_bytes: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(foto_bytes).decode()}"


def identificar_especie(foto_bytes: bytes) -> dict:
    lista_texto = "\n".join(
        f"- {e['nombre_comun']} ({e['nombre_cientifico']}) - {e['categoria']}"
        for e in _especies_referencia()
    )
    prompt = (
        "Observa esta imagen de un animal reportado en Colombia. "
        "Aquí tienes una lista de referencia de especies de Colombia (no es exhaustiva):\n"
        f"{lista_texto}\n\n"
        "Identifica la especie más probable (puede o no estar en la lista). Si no puedes "
        "determinarlo con certeza, indica confianza baja, no inventes datos."
    )
    mensaje = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _foto_a_data_url(foto_bytes)}},
        ]
    )

    try:
        modelo_estructurado = _modelo().with_structured_output(_EspecieIdentificada)
        resultado = modelo_estructurado.invoke([mensaje])
        return {**_ESPECIE_FALLBACK, **resultado.model_dump()}
    except Exception:
        return dict(_ESPECIE_FALLBACK)


def redactar_resumen_hechos(datos: dict) -> str:
    prompt = (
        "Eres un asistente que redacta el resumen de hechos para una denuncia ambiental "
        "formal en Colombia. Con los siguientes datos, escribe un párrafo breve (3 a 5 "
        "frases), claro, formal y respetuoso, resumiendo lo ocurrido, sin inventar "
        "información que no esté en los datos:\n\n"
        f"{json.dumps(datos, ensure_ascii=False, default=str)}"
    )
    try:
        respuesta = _modelo().invoke(prompt)
        return str(respuesta.content).strip()
    except Exception:
        return (
            "Un ciudadano reportó, a través de FaunaAlerta Bot, una situación que podría "
            "afectar fauna silvestre amenazada, según los datos estructurados adjuntos a "
            "esta denuncia."
        )
