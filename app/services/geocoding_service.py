import httpx

from app.core.config import get_settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
BIGDATACLOUD_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
_EMPTY = {"direccion_aprox": None, "municipio": None, "departamento": None}


def _coords_validas(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def reverse_geocode(lat: float, lon: float) -> dict:
    """Convierte lat/lon en departamento/municipio.

    Usa BigDataCloud (sin API key, sin restricciones de IP de Vercel).
    Nominatim bloquea los IPs compartidos de plataformas serverless.
    """
    if not _coords_validas(lat, lon):
        return _EMPTY

    try:
        resp = httpx.get(
            BIGDATACLOUD_URL,
            params={"latitude": lat, "longitude": lon, "localityLanguage": "es"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        departamento = data.get("principalSubdivision")
        municipio = data.get("city") or data.get("locality")
        pais = data.get("countryName", "")
        partes = [p for p in [municipio, departamento, pais] if p]
        direccion = ", ".join(partes) if partes else None

        return {
            "direccion_aprox": direccion,
            "municipio": municipio,
            "departamento": departamento,
        }
    except Exception:
        return _EMPTY


def forward_geocode(direccion: str) -> dict | None:
    """Convierte una dirección de texto en lat/lon. Usa Nominatim como opción."""
    settings = get_settings()
    try:
        resp = httpx.get(
            f"{NOMINATIM_URL}/search",
            params={
                "q": f"{direccion}, Colombia",
                "format": "json",
                "addressdetails": 1,
                "limit": 1,
            },
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json()
        if not resultados:
            return None
        resultado = resultados[0]
        address = resultado.get("address", {})
        return {
            "lat": float(resultado["lat"]),
            "lon": float(resultado["lon"]),
            "direccion_aprox": resultado.get("display_name"),
            "municipio": address.get("city") or address.get("town") or address.get("county"),
            "departamento": address.get("state"),
        }
    except Exception:
        return None
