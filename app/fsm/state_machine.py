import base64
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationState,
    EntidadDestino,
    EspeciePredicha,
    EstadoFSM,
    Ubicacion,
)
from app.services import (
    email_service,
    entity_directory,
    gemini_service,
    geocoding_service,
    image_service,
    session_store,
)
from app.templates import letter_template

OPCIONES_TIPO_LUGAR = ["Casa", "Negocio", "Hotel", "Vía pública", "Zona rural/Finca", "Otro"]
OPCIONES_ESPECIE = ["Sí", "No, es otra especie", "No estoy seguro"]
OPCIONES_UBICACION = ["Sí, es correcta", "No, quiero corregirla"]
OPCIONES_ANONIMATO = ["Sí, anónima", "No, deseo dejar mis datos de contacto"]
OPCIONES_RESUMEN = ["Confirmar y enviar", "Cancelar"]


def _resp(
    mensajes: str | list[str],
    tipo_input_esperado: str,
    *,
    opciones: list[str] | None = None,
    estado: str = "",
    mapa: dict | None = None,
) -> ChatResponse:
    return ChatResponse(
        mensajes=mensajes if isinstance(mensajes, list) else [mensajes],
        tipo_input_esperado=tipo_input_esperado,
        opciones=opciones or [],
        estado_actual=str(estado),
        mapa=mapa,
    )


def _handle_esperando_foto(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo != "foto" or not request.foto_base64:
        return _resp(
            "Para iniciar tu denuncia, envíame una foto del animal o de la situación.",
            "foto",
            estado=state.estado,
        )

    foto_bytes = base64.b64decode(request.foto_base64)
    foto_comprimida = image_service.comprimir_foto(foto_bytes)
    state.foto_bytes_b64 = image_service.foto_a_base64(foto_comprimida)

    especie = gemini_service.identificar_especie(foto_comprimida)
    state.denuncia.especie_predicha = EspeciePredicha(
        nombre_comun=especie.get("nombre_comun", "Especie no identificada"),
        nombre_cientifico=especie.get("nombre_cientifico", "Desconocida"),
        categoria_amenaza=especie.get("categoria_amenaza", "no aplica"),
        nativa_colombia=especie.get("nativa_colombia"),
        confianza=especie.get("confianza", "baja"),
    )
    state.estado = EstadoFSM.CONFIRMAR_ESPECIE

    ep = state.denuncia.especie_predicha
    mensaje = (
        "Gracias. Analizando la imagen... 🔍\n"
        f"Creo que podría tratarse de: {ep.nombre_cientifico} ({ep.nombre_comun}) — "
        f"categoría de referencia: {ep.categoria_amenaza} (confianza {ep.confianza}). "
        "¿Es correcto?"
    )
    return _resp(mensaje, "botones", opciones=OPCIONES_ESPECIE, estado=state.estado)


def _handle_confirmar_especie(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "boton" and request.texto == "Sí":
        state.estado = EstadoFSM.ESPERANDO_UBICACION
        return _resp(
            "Perfecto. Ahora necesito tu ubicación para saber a qué autoridad ambiental "
            "dirigir la denuncia.",
            "ubicacion",
            estado=state.estado,
        )

    if request.tipo == "boton" and request.texto == "No estoy seguro":
        state.denuncia.especie_predicha.confianza = "baja"
        state.estado = EstadoFSM.ESPERANDO_UBICACION
        return _resp(
            "Entendido, quedará registrada como especie no identificada con certeza. "
            "Ahora necesito tu ubicación para saber a qué autoridad ambiental dirigir la "
            "denuncia.",
            "ubicacion",
            estado=state.estado,
        )

    if request.tipo == "boton" and request.texto == "No, es otra especie":
        return _resp(
            "Escribe el nombre de la especie correcta (común o científico).",
            "texto",
            estado=state.estado,
        )

    if request.tipo == "texto" and request.texto:
        state.denuncia.especie_predicha = EspeciePredicha(
            nombre_comun=request.texto,
            nombre_cientifico="Aportado por el denunciante",
            categoria_amenaza="no aplica",
            confianza="alta",
            fuente="usuario",
        )
        state.estado = EstadoFSM.ESPERANDO_UBICACION
        return _resp(
            "Gracias por la corrección. Ahora necesito tu ubicación para saber a qué "
            "autoridad ambiental dirigir la denuncia.",
            "ubicacion",
            estado=state.estado,
        )

    return _resp(
        "Por favor selecciona una opción.", "botones", opciones=OPCIONES_ESPECIE, estado=state.estado
    )


def _handle_esperando_ubicacion(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "ubicacion" and request.lat is not None and request.lon is not None:
        geo = geocoding_service.reverse_geocode(request.lat, request.lon)
        state.denuncia.ubicacion = Ubicacion(lat=request.lat, lon=request.lon, **geo)
    elif request.tipo == "texto" and request.texto:
        geo = geocoding_service.forward_geocode(request.texto)
        if geo is None:
            return _resp(
                "No pude encontrar esa dirección. ¿Puedes intentar con más detalle "
                "(ej. vereda/barrio, municipio, departamento)?",
                "texto",
                estado=state.estado,
            )
        state.denuncia.ubicacion = Ubicacion(**geo)
    else:
        return _resp(
            "Comparte tu ubicación o escribe la dirección aproximada.",
            "ubicacion",
            estado=state.estado,
        )

    state.estado = EstadoFSM.CONFIRMAR_UBICACION
    ubic = state.denuncia.ubicacion
    return _resp(
        f"Detecté que estás cerca de: {ubic.direccion_aprox or 'ubicación desconocida'}. "
        "¿Es correcta esta ubicación?",
        "botones",
        opciones=OPCIONES_UBICACION,
        estado=state.estado,
        mapa={"lat": ubic.lat, "lon": ubic.lon},
    )


def _handle_confirmar_ubicacion(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "boton" and request.texto == "Sí, es correcta":
        state.estado = EstadoFSM.TIPO_LUGAR
        return _resp(
            "¿Dónde se encuentra exactamente la situación? Elige una opción:",
            "botones",
            opciones=OPCIONES_TIPO_LUGAR,
            estado=state.estado,
        )

    if request.tipo == "boton" and request.texto == "No, quiero corregirla":
        state.estado = EstadoFSM.ESPERANDO_UBICACION
        return _resp(
            "De acuerdo, comparte de nuevo tu ubicación o escribe la dirección.",
            "ubicacion",
            estado=state.estado,
        )

    return _resp(
        "Por favor selecciona una opción.",
        "botones",
        opciones=OPCIONES_UBICACION,
        estado=state.estado,
    )


def _handle_tipo_lugar(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "boton" and request.texto in OPCIONES_TIPO_LUGAR:
        state.denuncia.tipo_lugar = request.texto
        state.estado = EstadoFSM.DESCRIPCION_LUGAR
        return _resp(
            "Cuéntame brevemente qué observaste en ese lugar (ej. tipo de negocio, "
            "condiciones del animal, etc.).",
            "texto",
            estado=state.estado,
        )

    return _resp(
        "Por favor elige una opción de la lista.",
        "botones",
        opciones=OPCIONES_TIPO_LUGAR,
        estado=state.estado,
    )


def _handle_descripcion_lugar(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "texto" and request.texto:
        state.denuncia.descripcion_lugar = request.texto
        state.estado = EstadoFSM.PREGUNTA_ANONIMATO
        return _resp(
            "Última pregunta: ¿quieres que esta denuncia sea ANÓNIMA?",
            "botones",
            opciones=OPCIONES_ANONIMATO,
            estado=state.estado,
        )

    return _resp("Por favor escribe una breve descripción.", "texto", estado=state.estado)


def _handle_pregunta_anonimato(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "boton" and request.texto == "Sí, anónima":
        state.denuncia.anonima = True
        return _ir_a_resumen(state)

    if request.tipo == "boton" and request.texto == "No, deseo dejar mis datos de contacto":
        state.denuncia.anonima = False
        state.estado = EstadoFSM.DATOS_CONTACTO
        return _resp(
            "Puedes escribir tu nombre y/o teléfono de contacto (opcional, escribe "
            "'omitir' si prefieres no darlos).",
            "texto",
            estado=state.estado,
        )

    return _resp(
        "Por favor selecciona una opción.",
        "botones",
        opciones=OPCIONES_ANONIMATO,
        estado=state.estado,
    )


def _handle_datos_contacto(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "texto" and request.texto:
        if request.texto.strip().lower() != "omitir":
            state.denuncia.contacto = request.texto
        return _ir_a_resumen(state)

    return _resp("Escribe tus datos de contacto o 'omitir'.", "texto", estado=state.estado)


def _ir_a_resumen(state: ConversationState) -> ChatResponse:
    departamento = state.denuncia.ubicacion.departamento if state.denuncia.ubicacion else None
    entidad = entity_directory.resolver_entidad(departamento)
    state.denuncia.entidad_destino = EntidadDestino(**entidad)
    state.estado = EstadoFSM.RESUMEN_DENUNCIA

    d = state.denuncia
    ep = d.especie_predicha
    ubic = d.ubicacion
    resumen = (
        "Listo, este es el resumen de tu denuncia:\n"
        f"- Especie: {ep.nombre_cientifico} ({ep.nombre_comun})\n"
        f"- Ubicación: {ubic.direccion_aprox}\n"
        f"- Tipo de lugar: {d.tipo_lugar}\n"
        f"- Descripción: {d.descripcion_lugar}\n"
        f"- Denuncia anónima: {'Sí' if d.anonima else 'No'}\n\n"
        f"¿Confirmas el envío a {entidad['nombre']}?"
    )
    return _resp(resumen, "botones", opciones=OPCIONES_RESUMEN, estado=state.estado)


def _handle_resumen_denuncia(state: ConversationState, request: ChatRequest) -> ChatResponse:
    if request.tipo == "boton" and request.texto == "Cancelar":
        state.estado = EstadoFSM.FINALIZADO
        return _resp(
            "De acuerdo, tu denuncia fue cancelada y no se envió nada.",
            "texto",
            estado=state.estado,
        )

    if request.tipo == "boton" and request.texto == "Confirmar y enviar":
        return _enviar_denuncia(state)

    return _resp(
        "Por favor selecciona una opción.",
        "botones",
        opciones=OPCIONES_RESUMEN,
        estado=state.estado,
    )


def _enviar_denuncia(state: ConversationState) -> ChatResponse:
    d = state.denuncia
    try:
        resumen_hechos = gemini_service.redactar_resumen_hechos(d.model_dump())
        asunto = letter_template.construir_asunto(d.model_dump())
        cuerpo = letter_template.construir_cuerpo(d.model_dump(), resumen_hechos)
        foto_bytes = (
            image_service.base64_a_foto(state.foto_bytes_b64) if state.foto_bytes_b64 else b""
        )

        email_service.enviar_denuncia(d.entidad_destino.correo, asunto, cuerpo, foto_bytes)

        d.texto_denuncia = cuerpo
        d.estado_envio = "enviado"
        d.intentos_envio += 1
        state.estado = EstadoFSM.FINALIZADO
        return _resp(
            "✅ Tu denuncia fue enviada exitosamente.\n"
            f"Número de radicado interno: {d.id}\n"
            "Gracias por proteger la fauna silvestre de Colombia.",
            "texto",
            estado=state.estado,
        )
    except Exception:
        d.intentos_envio += 1
        d.estado_envio = "fallido"
        state.estado = EstadoFSM.RESUMEN_DENUNCIA
        return _resp(
            "Tuvimos un problema enviando tu denuncia. ¿Quieres intentar de nuevo?",
            "botones",
            opciones=OPCIONES_RESUMEN,
            estado=state.estado,
        )


def _handle_fallback(state: ConversationState, request: ChatRequest) -> ChatResponse:
    state.estado = EstadoFSM.ESPERANDO_FOTO
    return _resp(
        "Ocurrió un problema con tu sesión, vamos a empezar de nuevo. Envíame una foto "
        "para iniciar tu denuncia.",
        "foto",
        estado=state.estado,
    )


# --- Secuencia de la conversación organizada como un grafo de LangGraph ---
#
# Cada estado de la FSM es un nodo. El enrutamiento desde START decide a qué nodo ir
# según el estado ya persistido de la sesión (cargado de Redis antes de invocar el
# grafo); cada nodo resuelve un único turno y termina en END, ya que la siguiente
# pausa ("esperar la respuesta del usuario") ocurre fuera del grafo, entre una
# petición HTTP y la siguiente.
#
# No se usa el checkpointer nativo de LangGraph (langgraph-checkpoint-redis) porque
# requiere el módulo RediSearch para crear sus índices, que no está disponible en el
# tier gratuito de Upstash. La persistencia real sigue a cargo de `session_store`
# (REST de Upstash), igual que antes.


class _GraphState(TypedDict):
    state: ConversationState
    request: ChatRequest
    response: ChatResponse


def _nodo(handler):
    def ejecutar(grafo_state: _GraphState) -> dict:
        respuesta = handler(grafo_state["state"], grafo_state["request"])
        return {"response": respuesta}

    return ejecutar


_NODOS: dict[EstadoFSM, str] = {
    EstadoFSM.ESPERANDO_FOTO: "esperando_foto",
    EstadoFSM.CONFIRMAR_ESPECIE: "confirmar_especie",
    EstadoFSM.ESPERANDO_UBICACION: "esperando_ubicacion",
    EstadoFSM.CONFIRMAR_UBICACION: "confirmar_ubicacion",
    EstadoFSM.TIPO_LUGAR: "tipo_lugar",
    EstadoFSM.DESCRIPCION_LUGAR: "descripcion_lugar",
    EstadoFSM.PREGUNTA_ANONIMATO: "pregunta_anonimato",
    EstadoFSM.DATOS_CONTACTO: "datos_contacto",
    EstadoFSM.RESUMEN_DENUNCIA: "resumen_denuncia",
}

_HANDLERS_POR_NODO = {
    "esperando_foto": _handle_esperando_foto,
    "confirmar_especie": _handle_confirmar_especie,
    "esperando_ubicacion": _handle_esperando_ubicacion,
    "confirmar_ubicacion": _handle_confirmar_ubicacion,
    "tipo_lugar": _handle_tipo_lugar,
    "descripcion_lugar": _handle_descripcion_lugar,
    "pregunta_anonimato": _handle_pregunta_anonimato,
    "datos_contacto": _handle_datos_contacto,
    "resumen_denuncia": _handle_resumen_denuncia,
    "fallback": _handle_fallback,
}


def _enrutar(grafo_state: _GraphState) -> str:
    return _NODOS.get(grafo_state["state"].estado, "fallback")


def _construir_grafo():
    builder = StateGraph(_GraphState)
    for nombre, handler in _HANDLERS_POR_NODO.items():
        builder.add_node(nombre, _nodo(handler))
        builder.add_edge(nombre, END)
    builder.add_conditional_edges(START, _enrutar, {n: n for n in _HANDLERS_POR_NODO})
    return builder.compile()


_GRAFO = _construir_grafo()


def procesar_mensaje(session_id: str, request: ChatRequest) -> ChatResponse:
    state = session_store.get_session(session_id)
    resultado = _GRAFO.invoke({"state": state, "request": request, "response": None})
    response = resultado["response"]

    if state.estado == EstadoFSM.FINALIZADO:
        session_store.clear_session(session_id)
    else:
        session_store.save_session(session_id, state)

    return response
