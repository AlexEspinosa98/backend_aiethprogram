import pytest

from app.models.schemas import DenunciaCompletaRequest
from app.services import denuncia_service

TINY_JPEG = bytes.fromhex("ffd8ffd9")


@pytest.fixture(autouse=True)
def _stub_services(monkeypatch):
    monkeypatch.setattr(
        denuncia_service.image_service, "comprimir_foto", lambda foto_bytes: foto_bytes
    )
    monkeypatch.setattr(
        denuncia_service.gemini_service,
        "redactar_resumen_hechos",
        lambda datos: "Resumen de prueba de los hechos.",
    )
    monkeypatch.setattr(
        denuncia_service.geocoding_service,
        "reverse_geocode",
        lambda lat, lon: {
            "direccion_aprox": "Vereda La Esperanza, Rionegro, Antioquia",
            "municipio": "Rionegro",
            "departamento": "Antioquia",
        },
    )

    enviados = []

    def _enviar_mock(destinatario, asunto, cuerpo, foto_bytes):
        enviados.append((destinatario, asunto, cuerpo))
        return "enviado"

    monkeypatch.setattr(denuncia_service.email_service, "enviar_denuncia", _enviar_mock)

    return enviados


def test_denuncia_con_especie_reconocida(monkeypatch, _stub_services):
    monkeypatch.setattr(
        denuncia_service.gemini_service,
        "identificar_especie",
        lambda foto_bytes: {
            "nombre_comun": "Oso de anteojos",
            "nombre_cientifico": "Tremarctos ornatus",
            "categoria_amenaza": "VU",
            "nativa_colombia": True,
            "confianza": "alta",
        },
    )

    payload = DenunciaCompletaRequest(
        lat=6.15,
        lon=-75.38,
        tipo_lugar="Negocio",
        descripcion_lugar="Restaurante con el animal en una jaula",
        anonima=True,
    )
    resultado = denuncia_service.procesar_denuncia_completa(payload, foto_bytes=TINY_JPEG)

    assert resultado.estado_envio == "enviado"
    assert resultado.especie.nombre_cientifico == "Tremarctos ornatus"
    assert resultado.radicado.startswith("FA-")
    assert resultado.correo.asunto != ""
    assert len(_stub_services) == 1


def test_denuncia_especie_no_reconocida_no_bloquea(monkeypatch, _stub_services):
    monkeypatch.setattr(
        denuncia_service.gemini_service,
        "identificar_especie",
        lambda foto_bytes: {
            "nombre_comun": "Especie no identificada",
            "nombre_cientifico": "Desconocida",
            "categoria_amenaza": "no aplica",
            "nativa_colombia": None,
            "confianza": "baja",
        },
    )

    payload = DenunciaCompletaRequest(lat=6.15, lon=-75.38)
    resultado = denuncia_service.procesar_denuncia_completa(payload, foto_bytes=TINY_JPEG)

    assert resultado.estado_envio == "enviado"
    assert resultado.especie.confianza == "baja"


def test_denuncia_sin_foto(_stub_services):
    payload = DenunciaCompletaRequest(lat=6.15, lon=-75.38, descripcion_lugar="Sin foto disponible")
    resultado = denuncia_service.procesar_denuncia_completa(payload, foto_bytes=None)

    assert resultado.especie is None
    assert resultado.estado_envio == "enviado"
