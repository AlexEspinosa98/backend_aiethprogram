from fastapi import APIRouter

from app.models.schemas import DenunciaCompletaRequest, DenunciaCompletaResponse
from app.services.denuncia_service import procesar_denuncia_completa

router = APIRouter()


@router.post("/denuncias", response_model=DenunciaCompletaResponse)
def crear_denuncia(payload: DenunciaCompletaRequest) -> DenunciaCompletaResponse:
    return procesar_denuncia_completa(payload)
