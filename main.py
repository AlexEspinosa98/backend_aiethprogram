from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import chat, denuncias

settings = get_settings()

app = FastAPI(title="FaunaAlerta Bot API")

allowed_origins = [origin.strip() for origin in settings.allowed_origin.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(denuncias.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
