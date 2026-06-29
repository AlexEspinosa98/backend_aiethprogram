from fastapi.testclient import TestClient

import app.routers.denuncias as denuncias_router
from app.models.schemas import CorreoBorrador, DenunciaCompletaResponse, EntidadDestino
from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_denuncias_endpoint_esta_montado(monkeypatch):
    monkeypatch.setattr(
        denuncias_router,
        "procesar_denuncia_completa",
        lambda payload: DenunciaCompletaResponse(
            radicado="FA-2026-TEST01",
            mensaje="ok",
            especie=None,
            ubicacion=None,
            entidad_destino=EntidadDestino(nombre="CORNARE", correo="demo@example.com"),
            estado_envio="simulado",
            correo=CorreoBorrador(asunto="Asunto de prueba", cuerpo="Cuerpo de prueba"),
        ),
    )

    resp = client.post("/api/denuncias", json={"descripcion_lugar": "prueba"})
    assert resp.status_code == 200
    assert resp.json()["radicado"] == "FA-2026-TEST01"
