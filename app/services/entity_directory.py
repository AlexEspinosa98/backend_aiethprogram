import json
import unicodedata
from pathlib import Path

from app.core.config import get_settings

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "entidades_car.json"


def _normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _entidades() -> list[dict]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def resolver_entidad(departamento: str | None) -> dict:
    settings = get_settings()

    entidad_resuelta = None
    if departamento:
        objetivo = _normalizar(departamento)
        for entidad in _entidades():
            if _normalizar(entidad["departamento"]) == objetivo:
                entidad_resuelta = entidad
                break

    if entidad_resuelta is None:
        entidad_resuelta = {
            "departamento": departamento or "desconocido",
            "entidad": "Entidad ambiental nacional (respaldo)",
            "correo": settings.default_fallback_email,
        }

    correo_final = settings.demo_override_email or entidad_resuelta["correo"]
    return {"nombre": entidad_resuelta["entidad"], "correo": correo_final}
