from fastapi import APIRouter

from app.fsm.state_machine import procesar_mensaje
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat/message", response_model=ChatResponse)
def chat_message(request: ChatRequest) -> ChatResponse:
    return procesar_mensaje(request.session_id, request)
