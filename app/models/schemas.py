from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class EstadoFSM(StrEnum):
    ESPERANDO_FOTO = "ESPERANDO_FOTO"
    ANALIZANDO_ESPECIE = "ANALIZANDO_ESPECIE"
    CONFIRMAR_ESPECIE = "CONFIRMAR_ESPECIE"
    ESPERANDO_UBICACION = "ESPERANDO_UBICACION"
    CONFIRMAR_UBICACION = "CONFIRMAR_UBICACION"
    TIPO_LUGAR = "TIPO_LUGAR"
    DESCRIPCION_LUGAR = "DESCRIPCION_LUGAR"
    PREGUNTA_ANONIMATO = "PREGUNTA_ANONIMATO"
    DATOS_CONTACTO = "DATOS_CONTACTO"
    RESUMEN_DENUNCIA = "RESUMEN_DENUNCIA"
    ENVIANDO = "ENVIANDO"
    FINALIZADO = "FINALIZADO"


TipoInput = Literal["texto", "foto", "ubicacion", "boton"]
TipoInputEsperado = Literal["texto", "botones", "foto", "ubicacion"]


class ChatRequest(BaseModel):
    session_id: str
    tipo: TipoInput
    texto: str | None = None
    foto_base64: str | None = None
    lat: float | None = None
    lon: float | None = None


class ChatResponse(BaseModel):
    mensajes: list[str]
    tipo_input_esperado: TipoInputEsperado
    opciones: list[str] = Field(default_factory=list)
    estado_actual: str
    mapa: dict | None = None


class EspeciePredicha(BaseModel):
    nombre_comun: str
    nombre_cientifico: str
    categoria_amenaza: str
    nativa_colombia: bool | None = None
    confianza: Literal["alta", "media", "baja"]
    fuente: str = "gemini-vision"


class Ubicacion(BaseModel):
    lat: float
    lon: float
    direccion_aprox: str | None = None
    municipio: str | None = None
    departamento: str | None = None


class EntidadDestino(BaseModel):
    nombre: str
    correo: str


class Denuncia(BaseModel):
    id: str
    timestamp: str
    canal: Literal["web"] = "web"
    anonima: bool
    contacto: str | None = None
    foto_url: str | None = None
    especie_predicha: EspeciePredicha | None = None
    ubicacion: Ubicacion | None = None
    tipo_lugar: str | None = None
    descripcion_lugar: str | None = None
    entidad_destino: EntidadDestino | None = None
    texto_denuncia: str | None = None
    estado_envio: Literal["pendiente", "enviado", "fallido"] = "pendiente"
    intentos_envio: int = 0


class ConversationState(BaseModel):
    estado: EstadoFSM = EstadoFSM.ESPERANDO_FOTO
    foto_bytes_b64: str | None = None
    denuncia: Denuncia
