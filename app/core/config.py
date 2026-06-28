from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # Upstash Redis (estado de la conversación)
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    session_ttl_seconds: int = 3600

    # SMTP (opcional por ahora: si falta host/user/password, el envío se simula
    # imprimiendo el correo en los logs en vez de mandarlo de verdad)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "FaunaAlerta Bot <no-reply@example.com>"

    # Geocodificación
    nominatim_user_agent: str = "FaunaAlertaBot/1.0 (contacto@example.com)"

    # Entidades / envío
    default_fallback_email: str
    demo_override_email: str | None = None

    # Frontend
    allowed_origin: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
