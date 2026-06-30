import uuid
from datetime import datetime, timezone

from app.models.schemas import (
    CorreoBorrador,
    Denuncia,
    DenunciaCompletaRequest,
    DenunciaCompletaResponse,
    EntidadDestino,
    EspeciePredicha,
    Ubicacion,
)
from app.services import (
    email_service,
    entity_directory,
    gemini_service,
    geocoding_service,
    image_service,
)
from app.templates import letter_template


def _nuevo_radicado() -> str:
    year = datetime.now(timezone.utc).year
    return f"FA-{year}-{uuid.uuid4().hex[:6].upper()}"


def _resolver_ubicacion(payload: DenunciaCompletaRequest) -> Ubicacion | None:
    if payload.lat is not None and payload.lon is not None:
        geo = geocoding_service.reverse_geocode(payload.lat, payload.lon)
        return Ubicacion(lat=payload.lat, lon=payload.lon, **geo)

    if payload.direccion:
        geo = geocoding_service.forward_geocode(payload.direccion)
        if geo is not None:
            return Ubicacion(**geo)

    return None


def _identificar_especie(foto_bytes: bytes | None) -> tuple[EspeciePredicha | None, bytes]:
    if not foto_bytes:
        return None, b""

    comprimida = image_service.comprimir_foto(foto_bytes)
    especie = gemini_service.identificar_especie(comprimida)
    especie_predicha = EspeciePredicha(
        nombre_comun=especie.get("nombre_comun", "Especie no identificada"),
        nombre_cientifico=especie.get("nombre_cientifico", "Desconocida"),
        categoria_amenaza=especie.get("categoria_amenaza", "no aplica"),
        nativa_colombia=especie.get("nativa_colombia"),
        confianza=especie.get("confianza", "baja"),
    )
    # Nunca se bloquea ni se informa como error si la especie no se reconoce: se
    # sigue adelante igual con "Especie no identificada" / confianza baja.
    return especie_predicha, comprimida


def _construir_mensaje(especie, entidad_nombre: str) -> str:
    if especie is None:
        return (
            f"✅ Tu denuncia fue procesada y enviada a {entidad_nombre}. "
            "No se aportó fotografía, así que no se pudo identificar la especie. "
            "Gracias por proteger la fauna silvestre de Colombia."
        )

    if especie.confianza == "baja":
        return (
            f"✅ Tu denuncia fue procesada y enviada a {entidad_nombre}. "
            f"Se recibió la foto, pero no fue posible identificar la especie con certeza "
            f"(posiblemente {especie.nombre_comun}). "
            "Gracias por proteger la fauna silvestre de Colombia."
        )

    return (
        f"✅ Tu denuncia fue procesada y enviada a {entidad_nombre}.\n"
        f"Animal identificado: {especie.nombre_comun} ({especie.nombre_cientifico}) — "
        f"categoría de amenaza: {especie.categoria_amenaza} — "
        f"confianza: {especie.confianza}.\n"
        "Gracias por proteger la fauna silvestre de Colombia."
    )


def procesar_denuncia_completa(
    payload: DenunciaCompletaRequest, foto_bytes: bytes | None = None
) -> DenunciaCompletaResponse:
    especie_predicha, foto_final = _identificar_especie(foto_bytes)
    ubicacion = _resolver_ubicacion(payload)

    departamento = ubicacion.departamento if ubicacion else None
    entidad = entity_directory.resolver_entidad(departamento)
    entidad_destino = EntidadDestino(**entidad)

    denuncia = Denuncia(
        id=_nuevo_radicado(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        canal="api",
        anonima=payload.anonima,
        contacto=None if payload.anonima else payload.contacto,
        especie_predicha=especie_predicha,
        ubicacion=ubicacion,
        tipo_lugar=payload.tipo_lugar,
        descripcion_lugar=payload.descripcion_lugar,
        entidad_destino=entidad_destino,
    )

    resumen_hechos = gemini_service.redactar_resumen_hechos(denuncia.model_dump())
    asunto = letter_template.construir_asunto(denuncia.model_dump())
    cuerpo = letter_template.construir_cuerpo(denuncia.model_dump(), resumen_hechos)

    try:
        estado_envio = email_service.enviar_denuncia(
            entidad_destino.correo, asunto, cuerpo, foto_final
        )
    except Exception:
        estado_envio = "fallido"

    return DenunciaCompletaResponse(
        radicado=denuncia.id,
        mensaje=_construir_mensaje(especie_predicha, entidad_destino.nombre),
        especie=especie_predicha,
        ubicacion=ubicacion,
        entidad_destino=entidad_destino,
        estado_envio=estado_envio,
        correo=CorreoBorrador(asunto=asunto, cuerpo=cuerpo),
    )
