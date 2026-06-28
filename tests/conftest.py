import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://example.invalid")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-token")
os.environ.setdefault("SMTP_HOST", "smtp.example.invalid")
os.environ.setdefault("SMTP_USER", "test@example.invalid")
os.environ.setdefault("SMTP_PASSWORD", "test-password")
os.environ.setdefault("SMTP_FROM", "FaunaAlerta Bot <no-reply@example.invalid>")
os.environ.setdefault("DEFAULT_FALLBACK_EMAIL", "fallback@example.invalid")
os.environ.setdefault("DEMO_OVERRIDE_EMAIL", "demo@example.invalid")
