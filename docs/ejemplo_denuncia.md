# Ejemplo completo de denuncia — FaunaAlerta Bot

> Traza paso a paso qué hace el backend con el curl exacto que tienes, desde que llega
> la foto hasta el correo que se envía a la entidad ambiental.

---

## 1. El curl (está correcto ✅)

```bash
curl -X POST 'https://backend-aiethprogram.vercel.app/api/denuncias' \
  -H 'accept: application/json' \
  -F 'foto=@OIP.webp;type=image/webp' \
  -F 'lat=11.22493' \
  -F 'lon=-74.18444' \
  -F 'tipo_lugar=negocio' \
  -F 'descripcion_lugar=es un negocio donde tiene pajaros muy grandes y encerrados a mala calidad' \
  -F 'anonima=true'
```

> **Nota sobre el WebP:** el backend lo acepta sin problema (Pillow lo convierte
> internamente a JPEG para reducir tamaño y pasárselo a Gemini).
> Si prefieres, puedes usar `@foto.jpg;type=image/jpeg` — el resultado es el mismo.

---

## 2. Lo que hace el backend con eso (paso a paso)

```
FOTO recibida (WebP)
    │
    ▼
Pillow: redimensiona a max 800px y convierte a JPEG (~70-150 KB)
    │
    ▼
Gemini Vision: "¿qué animal es este?"
   → nombre_comun, nombre_cientifico, categoria_amenaza, confianza
    │
    ▼
BigDataCloud: lat=11.22493 lon=-74.18444
   → municipio: Santa Marta
   → departamento: Magdalena
    │
    ▼
entidades_car.json: Magdalena → CORPAMAG
   → correo: [el que configures en entidades_car.json o DEMO_OVERRIDE_EMAIL]
    │
    ▼
Gemini texto: redacta 3-5 frases formales del "resumen de los hechos"
    │
    ▼
letter_template: arma asunto + cuerpo completo de la carta
    │
    ▼
SMTP (o log si no está configurado): envía carta + foto adjunta
    │
    ▼
Response JSON con radicado, especie, carta borrador
```

---

## 3. Carta formal generada (ejemplo real con tus datos)

> Lo que llega en `correo.asunto` y `correo.cuerpo` del response.

### Asunto

```
Denuncia ciudadana ambiental - Posible afectación a fauna silvestre amenazada -
Guacamaya roja - Santa Marta, Magdalena
```

### Cuerpo

```
Señores
CORPAMAG

De manera anónima, un ciudadano reporta a través del sistema FaunaAlerta Bot
(canal web) los siguientes hechos:

1. Fecha y hora del reporte: 2026-06-30T15:30:00-05:00
2. Ubicación reportada: Santa Marta, Magdalena, Colombia
   Coordenadas GPS: 11.22493, -74.18444
   (mapa: https://www.openstreetmap.org/?mlat=11.22493&mlon=-74.18444)
3. Tipo de lugar: negocio
   Descripción aportada por el denunciante:
   "es un negocio donde tiene pajaros muy grandes y encerrados a mala calidad"
4. Especie presuntamente involucrada: Ara macao (Guacamaya roja)
   Categoría de amenaza de referencia: LC
   Identificación automática (no oficial) - confianza: media
5. Resumen de los hechos: El denunciante reporta la presencia de aves silvestres
   de gran tamaño en condiciones inadecuadas de cautiverio en un establecimiento
   comercial en Santa Marta. La situación podría constituir una infracción a la
   normativa ambiental vigente relacionada con el tráfico y tenencia ilegal de
   fauna silvestre.
6. Evidencia adjunta: fotografía aportada por el denunciante (archivo adjunto)
7. Datos de contacto del denunciante: Denuncia anónima. No se registran datos
   de contacto.

Se solicita a la entidad competente adelantar las verificaciones y acciones a que
haya lugar conforme a la normativa ambiental vigente.

-- Reporte generado automáticamente por FaunaAlerta Bot a partir de información
   suministrada voluntariamente por un ciudadano vía formulario web.
   Radicado interno: FA-2026-AB12CD
```

---

## 4. Response JSON que devuelve el endpoint

```json
{
  "radicado": "FA-2026-AB12CD",
  "mensaje": "✅ Tu denuncia fue procesada y enviada a CORPAMAG.\nAnimal identificado: Guacamaya roja (Ara macao) — categoría de amenaza: LC — confianza: media.\nGracias por proteger la fauna silvestre de Colombia.",
  "especie": {
    "nombre_comun": "Guacamaya roja",
    "nombre_cientifico": "Ara macao",
    "categoria_amenaza": "LC",
    "nativa_colombia": true,
    "confianza": "media",
    "fuente": "gemini-vision"
  },
  "ubicacion": {
    "lat": 11.22493,
    "lon": -74.18444,
    "direccion_aprox": "Santa Marta, Magdalena, Colombia",
    "municipio": "Santa Marta",
    "departamento": "Magdalena"
  },
  "entidad_destino": {
    "nombre": "CORPAMAG",
    "correo": "contactenos@corpamag.gov.co"
  },
  "estado_envio": "simulado",
  "correo": {
    "asunto": "Denuncia ciudadana ambiental - ...",
    "cuerpo": "Señores\nCORPAMAG\n\n..."
  }
}
```

---

## 5. Qué significa `estado_envio`

| Valor | Significa |
|---|---|
| `"enviado"` | El correo salió por SMTP a CORPAMAG. |
| `"simulado"` | SMTP no está configurado (faltan `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` en Vercel) — el correo se imprimió en los logs pero no se envió. |
| `"fallido"` | SMTP sí estaba configurado pero falló el envío (ej. credenciales incorrectas). |

---

## 6. Pendiente antes de producción

| Paso | Qué hacer |
|---|---|
| **Correo de CORPAMAG** | ✅ Ya está: `contactenos@corpamag.gov.co`. **Importante:** define `DEMO_OVERRIDE_EMAIL` en Vercel mientras haces pruebas para que los correos de prueba lleguen a ti y no a CORPAMAG de verdad. |
| **SMTP** | Configurar `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` en Vercel para que el correo salga de verdad. |
| **Modelo Gemini** | Si `gemini-2.0-flash` da quota 0, cambiar `GEMINI_MODEL=gemini-1.5-flash` en Vercel o crear una API key nueva desde [aistudio.google.com](https://aistudio.google.com). |
| **Correos de las 33 CAR** | Completar `app/data/entidades_car.json` con los emails oficiales verificados de cada Corporación Autónoma Regional. |

---

## 7. Cómo verificar que el correo quedó bien (sin SMTP)

Mientras el SMTP está en modo simulado, el contenido completo del correo aparece en
los **logs de la función en Vercel** (Deployments → la última función → Logs).
Busca la línea:

```
=== SMTP desactivado: ejemplo del correo que se habría enviado ===
```

Ahí verás exactamente el asunto, el cuerpo y el tamaño del adjunto que se habrían
enviado, para validar que la carta esté bien antes de activar el SMTP real.
