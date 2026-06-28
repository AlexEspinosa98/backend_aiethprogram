import httpx

from app.core.config import get_settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org"


def reverse_geocode(lat: float, lon: float) -> dict:
    settings = get_settings()
    resp = httpx.get(
        f"{NOMINATIM_URL}/reverse",
        params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
        headers={"User-Agent": settings.nominatim_user_agent},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    address = data.get("address", {})
    return {
        "direccion_aprox": data.get("display_name"),
        "municipio": address.get("city") or address.get("town") or address.get("county"),
        "departamento": address.get("state"),
    }


def forward_geocode(direccion: str) -> dict | None:
    settings = get_settings()
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
