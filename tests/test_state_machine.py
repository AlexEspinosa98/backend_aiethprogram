import base64

import pytest

from app.fsm import state_machine
from app.models.schemas import ChatRequest, EstadoFSM

_TINY_JPEG_BYTES = bytes.fromhex("ffd8ffd9")
TINY_JPEG_B64 = base64.b64encode(_TINY_JPEG_BYTES).decode()


@pytest.fixture(autouse=True)
def _stub_services(monkeypatch):
    store: dict = {}

    monkeypatch.setattr(
        state_machine.session_store,
        "get_session",
        lambda sid: store.get(sid) or state_machine.session_store._default_state(),
    )
    monkeypatch.setattr(
        state_machine.session_store, "save_session", lambda sid, s: store.__setitem__(sid, s)
    )
    monkeypatch.setattr(
        state_machine.session_store, "clear_session", lambda sid: store.pop(sid, None)
    )

    monkeypatch.setattr(
        state_machine.gemini_service,
        "identificar_especie",
        lambda foto_bytes: {
            "nombre_comun": "Oso de anteojos",
            "nombre_cientifico": "Tremarctos ornatus",
            "categoria_amenaza": "VU",
            "nativa_colombia": True,
            "confianza": "alta",
        },
    )
    monkeypatch.setattr(
        state_machine.gemini_service,
        "redactar_resumen_hechos",
        lambda datos: "Resumen de prueba de los hechos.",
    )
    monkeypatch.setattr(
        state_machine.gemini_service,
        "responder_chat_abierto",
        lambda texto: f"(respuesta simulada a: {texto})",
    )
    monkeypatch.setattr(
        state_machine.geocoding_service,
        "reverse_geocode",
        lambda lat, lon: {
            "direccion_aprox": "Vereda La Esperanza, Rionegro, Antioquia",
            "municipio": "Rionegro",
            "departamento": "Antioquia",
        },
    )
    monkeypatch.setattr(state_machine.image_service, "comprimir_foto", lambda foto_bytes: foto_bytes)

    enviados = []

    def _enviar_mock(destinatario, asunto, cuerpo, foto_bytes):
        enviados.append((destinatario, asunto, cuerpo))
        return "enviado"

    monkeypatch.setattr(state_machine.email_service, "enviar_denuncia", _enviar_mock)

    return enviados


def test_chat_abierto_antes_de_la_foto(_stub_services):
    session_id = "test-session-open"

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="texto", texto="hola, qué es esto?")
    )
    assert r.estado_actual == EstadoFSM.ESPERANDO_FOTO
    assert r.tipo_input_esperado == "foto"
    assert "respuesta simulada" in r.mensajes[0]

    # la sesión sigue abierta: el usuario puede seguir charlando antes de enviar la foto
    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="texto", texto="ok, ya entendí")
    )
    assert r.estado_actual == EstadoFSM.ESPERANDO_FOTO

    # y en cualquier momento puede enviar la foto para arrancar la denuncia
    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="foto", foto_base64=TINY_JPEG_B64)
    )
    assert r.estado_actual == EstadoFSM.CONFIRMAR_ESPECIE


def test_flujo_completo_anonimo(_stub_services):
    session_id = "test-session-1"

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="foto", foto_base64=TINY_JPEG_B64)
    )
    assert r.estado_actual == EstadoFSM.CONFIRMAR_ESPECIE
    assert "Tremarctos ornatus" in r.mensajes[0]

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Sí")
    )
    assert r.estado_actual == EstadoFSM.ESPERANDO_UBICACION

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="ubicacion", lat=6.15, lon=-75.38)
    )
    assert r.estado_actual == EstadoFSM.CONFIRMAR_UBICACION
    assert r.mapa == {"lat": 6.15, "lon": -75.38}

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Sí, es correcta")
    )
    assert r.estado_actual == EstadoFSM.TIPO_LUGAR

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Negocio")
    )
    assert r.estado_actual == EstadoFSM.DESCRIPCION_LUGAR

    r = state_machine.procesar_mensaje(
        session_id,
        ChatRequest(
            session_id=session_id,
            tipo="texto",
            texto="Restaurante con el animal en una jaula pequeña",
        ),
    )
    assert r.estado_actual == EstadoFSM.PREGUNTA_ANONIMATO

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Sí, anónima")
    )
    assert r.estado_actual == EstadoFSM.RESUMEN_DENUNCIA

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Confirmar y enviar")
    )
    assert r.estado_actual == EstadoFSM.FINALIZADO
    assert "radicado" in r.mensajes[0].lower()


def test_correccion_especie_y_ubicacion_no_mapeada(_stub_services):
    session_id = "test-session-2"

    state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="foto", foto_base64=TINY_JPEG_B64)
    )
    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="No, es otra especie")
    )
    assert r.tipo_input_esperado == "texto"

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="texto", texto="Tigrillo")
    )
    assert r.estado_actual == EstadoFSM.ESPERANDO_UBICACION

    state_machine.geocoding_service.reverse_geocode = lambda lat, lon: {
        "direccion_aprox": "Lugar sin departamento reconocido",
        "municipio": None,
        "departamento": None,
    }
    state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="ubicacion", lat=0.0, lon=0.0)
    )
    state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Sí, es correcta")
    )
    state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="boton", texto="Casa")
    )
    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="texto", texto="Animal en un patio")
    )
    assert r.estado_actual == EstadoFSM.PREGUNTA_ANONIMATO

    r = state_machine.procesar_mensaje(
        session_id,
        ChatRequest(
            session_id=session_id, tipo="boton", texto="No, deseo dejar mis datos de contacto"
        ),
    )
    assert r.estado_actual == EstadoFSM.DATOS_CONTACTO

    r = state_machine.procesar_mensaje(
        session_id, ChatRequest(session_id=session_id, tipo="texto", texto="omitir")
    )
    assert r.estado_actual == EstadoFSM.RESUMEN_DENUNCIA
    # sin departamento reconocido, debe resolver a la entidad nacional de respaldo
    assert "Entidad ambiental nacional (respaldo)" in r.mensajes[-1]
