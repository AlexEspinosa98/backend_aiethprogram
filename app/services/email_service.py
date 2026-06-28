import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings


def enviar_denuncia(destinatario: str, asunto: str, cuerpo: str, foto_bytes: bytes) -> None:
    settings = get_settings()

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
