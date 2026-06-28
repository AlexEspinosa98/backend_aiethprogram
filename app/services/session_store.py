import uuid
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.models.schemas import ConversationState, Denuncia, EstadoFSM


def _headers() -> dict:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.upstash_redis_rest_token}"}


def _new_radicado() -> str:
    year = datetime.now(timezone.utc).year
    return f"FA-{year}-{uuid.uuid4().hex[:6].upper()}"


def _default_state() -> ConversationState:
    denuncia = Denuncia(
        id=_new_radicado(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        anonima=False,
    )
    return ConversationState(estado=EstadoFSM.ESPERANDO_FOTO, denuncia=denuncia)


def get_session(session_id: str) -> ConversationState:
    settings = get_settings()
    resp = httpx.get(
        f"{settings.upstash_redis_rest_url}/get/{session_id}",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json().get("result")
    if raw is None:
        return _default_state()
    return ConversationState.model_validate_json(raw)


def save_session(session_id: str, state: ConversationState) -> None:
    settings = get_settings()
    resp = httpx.post(
        f"{settings.upstash_redis_rest_url}/set/{session_id}",
        headers=_headers(),
        params={"EX": settings.session_ttl_seconds},
        content=state.model_dump_json().encode("utf-8"),
        timeout=10,
    )
    resp.raise_for_status()


def clear_session(session_id: str) -> None:
    settings = get_settings()
    resp = httpx.get(
        f"{settings.upstash_redis_rest_url}/del/{session_id}",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
