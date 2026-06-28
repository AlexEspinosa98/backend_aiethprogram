import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings


def _smtp_configurado(settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def enviar_denuncia(destinatario: str, asunto: str, cuerpo: str, foto_bytes: bytes) -> None:
    settings = get_settings()

    if not _smtp_configurado(settings):
        print(
            "=== SMTP desactivado: ejemplo del correo que se habría enviado ===\n"
            f"Para: {destinatario}\n"
            f"De: {settings.smtp_from}\n"
            f"Asunto: {asunto}\n\n"
            f"{cuerpo}\n"
            f"[Adjunto: foto de {len(foto_bytes)} bytes]\n"
            "=== fin del ejemplo (no se envió nada de verdad) ==="
        )
        return

    mensaje = MIMEMultipart()
    mensaje["From"] = settings.smtp_from
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.attach(MIMEText(cuerpo, "plain", "utf-8"))

    if foto_bytes:
        adjunto = MIMEApplication(foto_bytes, Name="evidencia.jpg")
        adjunto["Content-Disposition"] = 'attachment; filename="evidencia.jpg"'
        mensaje.attach(adjunto)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as servidor:
        servidor.starttls()
        servidor.login(settings.smtp_user, settings.smtp_password)
        servidor.send_message(mensaje)
