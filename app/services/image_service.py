import base64
import io

from PIL import Image

MAX_DIMENSION = 800
JPEG_QUALITY = 70


def comprimir_foto(foto_bytes: bytes) -> bytes:
    imagen = Image.open(io.BytesIO(foto_bytes))
    imagen = imagen.convert("RGB")
    imagen.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def foto_a_base64(foto_bytes: bytes) -> str:
    return base64.b64encode(foto_bytes).decode("utf-8")


def base64_a_foto(foto_b64: str) -> bytes:
    return base64.b64decode(foto_b64)
