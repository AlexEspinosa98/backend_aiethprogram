# API Reference — FaunaAlerta Bot Backend

> Referencia técnica exacta de qué recibe y qué responde cada endpoint. Para el
> flujo narrado paso a paso (con ejemplos de conversación completa), ver
> [historia_usuario.md](historia_usuario.md). Para la arquitectura completa, ver
> [docs/plan-chatweb.md](docs/plan-chatweb.md).

## Endpoints

| Método | Ruta | Tipo |
|---|---|---|
| `POST` | `/api/chat/message` | Conversacional, con sesión (un turno por request) |
| `POST` | `/api/denuncias` | Un solo disparo, sin sesión (toda la info en un request) |
| `GET` | `/api/health` | Health check |

Todos los endpoints reciben/devuelven `application/json`.

---

## 1. `POST /api/chat/message`

### Qué recibe (`ChatRequest`)

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `session_id` | string | Sí | Identificador de la conversación. Generarlo una vez por sesión (ej. `crypto.randomUUID()`) y reusarlo en cada turno. |
| `tipo` | `"texto"` \| `"foto"` \| `"ubicacion"` \| `"boton"` | Sí | Qué tipo de dato manda este turno. |
| `texto` | string | Solo si `tipo` es `"texto"` o `"boton"` | Texto libre, o la etiqueta **exacta** de una opción recibida previamente (si `tipo: "boton"`). |
| `foto_base64` | string (base64) | Solo si `tipo: "foto"` | La foto, en base64 puro (sin el prefijo `data:image/...;base64,`). |
| `lat` | float | Solo si `tipo: "ubicacion"` | Latitud. |
| `lon` | float | Solo si `tipo: "ubicacion"` | Longitud. |

```json
{
  "session_id": "abc-123",
  "tipo": "foto",
  "texto": null,
  "foto_base64": "<base64>",
  "lat": null,
  "lon": null
}
```

### Qué responde (`ChatResponse`)

| Campo | Tipo | Siempre presente | Descripción |
|---|---|---|---|
| `mensajes` | string[] | Sí | Mensajes del bot a mostrar en orden, como burbujas. |
| `tipo_input_esperado` | `"texto"` \| `"foto"` \| `"ubicacion"` \| `"botones"` | Sí | Qué **control adicional** mostrar (la caja de texto debe estar siempre visible además de esto, ver `historia_usuario.md`). |
| `opciones` | string[] | Sí (vacío si no aplica) | Etiquetas de los botones a renderizar, solo relevante si `tipo_input_esperado: "botones"`. |
| `estado_actual` | string | Sí | Uno de los valores de la FSM (ver tabla abajo). Informativo/para depurar, no es necesario mostrarlo al usuario. |
| `mapa` | `{lat: float, lon: float}` \| `null` | Sí (puede ser `null`) | Coordenadas a mostrar en un mapa; solo viene poblado justo después de recibir la ubicación. |

```json
{
  "mensajes": ["Detecté que estás cerca de: Vereda La Esperanza, Rionegro, Antioquia. ¿Es correcta esta ubicación?"],
  "tipo_input_esperado": "botones",
  "opciones": ["Sí, es correcta", "No, quiero corregirla"],
  "estado_actual": "CONFIRMAR_UBICACION",
  "mapa": {"lat": 6.1521, "lon": -75.3838}
}
```

### Valores posibles de `estado_actual`

| Valor | Significado |
|---|---|
| `ESPERANDO_FOTO` | Estado inicial. Acepta foto (avanza) o texto libre (el bot conversa, sin avanzar). |
| `CONFIRMAR_ESPECIE` | Esperando que el usuario confirme, corrija o rechace la especie sugerida. |
| `ESPERANDO_UBICACION` | Esperando GPS (`tipo: "ubicacion"`) o una dirección escrita (`tipo: "texto"`). |
| `CONFIRMAR_UBICACION` | Esperando confirmación de la dirección detectada. |
| `TIPO_LUGAR` | Esperando un botón: `Casa`, `Negocio`, `Hotel`, `Vía pública`, `Zona rural/Finca` u `Otro`. |
| `DESCRIPCION_LUGAR` | Esperando texto libre describiendo lo observado. |
| `PREGUNTA_ANONIMATO` | Esperando botón: anónima o no. |
| `DATOS_CONTACTO` | Esperando texto con datos de contacto (u `"omitir"`). Solo se llega aquí si eligió no ser anónimo. |
| `RESUMEN_DENUNCIA` | Esperando botón: `Confirmar y enviar` o `Cancelar`. |
| `FINALIZADO` | La conversación terminó (enviada o cancelada). Cualquier mensaje nuevo con el mismo `session_id` reinicia el flujo desde `ESPERANDO_FOTO`. |

> `ANALIZANDO_ESPECIE` y `ENVIANDO` existen como nombres internos de la máquina de
> estados pero nunca se devuelven en `estado_actual`: ambos pasos se resuelven por
> completo dentro del mismo request (no son un turno separado de espera).

### Comparación de botones

Para `tipo: "boton"`, el backend compara `texto` contra listas fijas de opciones
(comparación exacta de string, con tildes). Hay que reenviar la etiqueta tal cual se
recibió en `opciones`, nunca un índice.

---

## 2. `POST /api/denuncias`

Un solo request con toda la información; no usa sesión ni Redis.

> **Content-Type: `multipart/form-data`** (no JSON).
> La foto se sube como archivo; el resto de campos son `Form` fields.
> En Swagger (`/docs`) aparece directamente un botón "Browse…" para seleccionar la foto
> y campos de texto para cada parámetro.

### Qué recibe (multipart/form-data)

| Campo | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `foto` | file (JPEG/PNG) | No | — | Si se omite, la denuncia se procesa sin identificación de especie. |
| `lat` | float | No | — | Latitud GPS. Preferido sobre `direccion` si ambos vienen. |
| `lon` | float | No | — | Longitud GPS. |
| `direccion` | string | No | — | Alternativa a `lat`/`lon`; se geocodifica con Nominatim. |
| `tipo_lugar` | string | No | — | Texto libre (ej. `Negocio`, `Casa`, `Hotel`, `Zona rural`). |
| `descripcion_lugar` | string | No | — | Breve descripción de lo observado. |
| `anonima` | bool | No | `true` | `false` = incluir los datos de `contacto` en la denuncia. |
| `contacto` | string | No | — | Nombre/teléfono del denunciante (se ignora si `anonima=true`). |

### Qué responde (`DenunciaCompletaResponse`)

| Campo | Tipo | Descripción |
|---|---|---|
| `radicado` | string | Identificador único de la denuncia, ej. `FA-2026-4F2A1B`. |
| `mensaje` | string | Mensaje de confirmación para mostrar al usuario. Nunca describe un fallo de identificación de especie como error. |
| `especie` | `EspeciePredicha \| null` | `null` si no se mandó foto. Si se mandó pero no se reconoció con certeza, viene igual con `confianza: "baja"` (nunca bloquea ni es un error). |
| `ubicacion` | `Ubicacion \| null` | `null` si no se pudo resolver ni por coordenadas ni por dirección. |
| `entidad_destino` | `EntidadDestino` | Siempre presente; si no se resolvió el departamento, cae en la entidad de respaldo (`DEFAULT_FALLBACK_EMAIL`). |
| `estado_envio` | `"enviado"` \| `"simulado"` \| `"fallido"` | `"simulado"` si el backend no tiene SMTP configurado (no es un error). |
| `correo` | `CorreoBorrador` | El borrador exacto (`asunto` + `cuerpo`) de la denuncia formal, enviada o no. |

```json
{
  "radicado": "FA-2026-4F2A1B",
  "mensaje": "Tu denuncia fue procesada y enviada a la entidad competente. Gracias por proteger la fauna silvestre de Colombia.",
  "especie": {
    "nombre_comun": "Oso de anteojos",
    "nombre_cientifico": "Tremarctos ornatus",
    "categoria_amenaza": "VU",
    "nativa_colombia": true,
    "confianza": "alta",
    "fuente": "gemini-vision"
  },
  "ubicacion": {
    "lat": 6.1521,
    "lon": -75.3838,
    "direccion_aprox": "Vereda La Esperanza, Rionegro, Antioquia",
    "municipio": "Rionegro",
    "departamento": "Antioquia"
  },
  "entidad_destino": {"nombre": "CORNARE", "correo": "PENDIENTE_VERIFICAR"},
  "estado_envio": "enviado",
  "correo": {
    "asunto": "Denuncia ciudadana ambiental - Posible afectación a fauna silvestre amenazada - Oso de anteojos - Rionegro, Antioquia",
    "cuerpo": "Señores\nCORNARE\n\nDe manera anónima, un ciudadano reporta..."
  }
}
```

---

## 3. `GET /api/health`

```json
{"status": "ok"}
```

Sin parámetros. Devuelve `200` si el proceso está vivo (si las variables de entorno
obligatorias faltan, la app ni siquiera arranca — ver `app/core/config.py`).

---

## Tipos anidados compartidos

| Tipo | Campos |
|---|---|
| `EspeciePredicha` | `nombre_comun` (str), `nombre_cientifico` (str), `categoria_amenaza` (str: `"CR"`\|`"EN"`\|`"VU"`\|`"no aplica"`), `nativa_colombia` (bool\|null), `confianza` (`"alta"`\|`"media"`\|`"baja"`), `fuente` (str, default `"gemini-vision"`) |
| `Ubicacion` | `lat` (float), `lon` (float), `direccion_aprox` (str\|null), `municipio` (str\|null), `departamento` (str\|null) |
| `EntidadDestino` | `nombre` (str), `correo` (str) |
| `CorreoBorrador` | `asunto` (str), `cuerpo` (str) |

## Errores

- **422 Unprocessable Entity:** validación de FastAPI/Pydantic — falta un campo
  requerido o el tipo no coincide (ej. `tipo` con un valor fuera de los 4 permitidos).
- **200 con `estado_envio: "fallido"`:** el procesamiento fue exitoso pero el envío
  del correo falló (ej. credenciales SMTP inválidas); no es un error HTTP, el
  `radicado` y el borrador ya existen igual.
- No hay otros códigos de error definidos hoy (sin autenticación, sin rate limiting).

---

## Cómo probar

### Swagger UI (en el navegador)

Abre **`https://tu-backend.vercel.app/docs`** (o `http://localhost:8000/docs` en local).

- `/api/health` → un solo clic en "Execute".
- `/api/denuncias` → el campo `foto` muestra un botón **Browse…** para subir el archivo directamente; el resto son campos de texto normales.
- `/api/chat/message` → pega el JSON en el body y ejecuta.

### curl — `/api/health`

```bash
curl https://tu-backend.vercel.app/api/health
```

### curl — `/api/denuncias` (con foto)

```bash
curl -X POST https://tu-backend.vercel.app/api/denuncias \
  -F "foto=@/ruta/a/foto.jpg" \
  -F "lat=6.1521" \
  -F "lon=-75.3838" \
  -F "tipo_lugar=Negocio" \
  -F "descripcion_lugar=Restaurante con el animal en una jaula pequeña en la entrada" \
  -F "anonima=true"
```

### curl — `/api/denuncias` (sin foto, solo descripción y ubicación)

```bash
curl -X POST https://tu-backend.vercel.app/api/denuncias \
  -F "lat=6.1521" \
  -F "lon=-75.3838" \
  -F "descripcion_lugar=Vi un animal herido en la vía" \
  -F "anonima=true"
```

### curl — `/api/denuncias` (con datos de contacto, no anónima)

```bash
curl -X POST https://tu-backend.vercel.app/api/denuncias \
  -F "foto=@/ruta/a/foto.jpg" \
  -F "lat=4.7110" \
  -F "lon=-74.0721" \
  -F "tipo_lugar=Casa" \
  -F "descripcion_lugar=Loro enjaulado en una vivienda del barrio" \
  -F "anonima=false" \
  -F "contacto=Juan Pérez, 310 000 0000"
```

### curl — `/api/chat/message` (flujo conversacional)

```bash
# 1. Enviar saludo (chat abierto antes de la foto)
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "texto", "texto": "hola, cómo funciona esto?"}'

# 2. Enviar foto (convierte foto a base64 primero)
FOTO_B64=$(base64 -i /ruta/a/foto.jpg | tr -d '\n')
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"test-001\", \"tipo\": \"foto\", \"foto_base64\": \"$FOTO_B64\"}"

# 3. Confirmar especie (usar el texto exacto del campo opciones)
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "boton", "texto": "Sí"}'

# 4. Compartir ubicación GPS
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "ubicacion", "lat": 6.1521, "lon": -75.3838}'

# 5. Confirmar ubicación
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "boton", "texto": "Sí, es correcta"}'

# 6. Tipo de lugar
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "boton", "texto": "Negocio"}'

# 7. Descripción
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "texto", "texto": "Restaurante con el animal en una jaula"}'

# 8. Anonimato
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "boton", "texto": "Sí, anónima"}'

# 9. Confirmar envío
curl -X POST https://tu-backend.vercel.app/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "tipo": "boton", "texto": "Confirmar y enviar"}'
```

> En macOS el comando `base64` incluye saltos de línea por defecto; el `tr -d '\n'`
> los elimina. En Linux: `base64 -w 0 /ruta/a/foto.jpg`. En Windows
> (PowerShell): `[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\foto.jpg"))`.
