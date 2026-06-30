from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import DenunciaCompletaRequest, DenunciaCompletaResponse
from app.services.denuncia_service import procesar_denuncia_completa

router = APIRouter()


@router.post("/denuncias", response_model=DenunciaCompletaResponse)
async def crear_denuncia(
    foto: UploadFile | None = File(None, description="Foto del animal o la situación (JPEG/PNG)."),
    lat: float | None = Form(None, description="Latitud GPS."),
    lon: float | None = Form(None, description="Longitud GPS."),
    direccion: str | None = Form(None, description="Alternativa a lat/lon: dirección en texto."),
    tipo_lugar: str | None = Form(None, description="Ej: Casa, Negocio, Hotel, Zona rural."),
    descripcion_lugar: str | None = Form(None, description="Breve descripción de lo observado."),
    anonima: bool = Form(True, description="True = no incluir datos de contacto en la denuncia."),
    contacto: str | None = Form(None, description="Nombre/teléfono (solo si anonima=false)."),
) -> DenunciaCompletaResponse:
    foto_bytes = await foto.read() if foto else None
    payload = DenunciaCompletaRequest(
        lat=lat,
        lon=lon,
        direccion=direccion,
        tipo_lugar=tipo_lugar,
        descripcion_lugar=descripcion_lugar,
        anonima=anonima,
        contacto=contacto,
    )
    return procesar_denuncia_completa(payload, foto_bytes=foto_bytes)
