# FaunaAlerta Bot — Backend

API en FastAPI que recibe los turnos de un chat web (foto, ubicación GPS, texto,
botones), identifica la especie en la foto con Gemini (vía LangChain), redacta una
denuncia formal y la envía por correo (SMTP) a la entidad ambiental competente en
Colombia.

Este repositorio es **solo backend**. El frontend (chat web) es otro proyecto que
consume esta API; ofrece dos formas de integrarse: un endpoint conversacional
(`POST /api/chat/message`) o uno de un solo disparo (`POST /api/denuncias`).

- **[api.md](api.md)** — referencia técnica de campos/tipos de cada endpoint.
- **[historia_usuario.md](historia_usuario.md)** — historia de usuario, flujo paso a
  paso y ejemplos de payloads reales.
- **[docs/plan-chatweb.md](docs/plan-chatweb.md)** — arquitectura completa, decisiones
  de diseño, límites de los tiers gratuitos y roadmap. Esta guía (README) es solo el
  resumen práctico para levantar el proyecto.

## Qué hay que crear/configurar (por servicio)

Todo tiene capa gratuita. Estos son los únicos servicios externos necesarios:

| Servicio | Para qué | Dónde se configura |
|---|---|---|
| **Google AI Studio** | Identificar la especie en la foto y redactar la denuncia (Gemini, vía LangChain) | `GEMINI_API_KEY` |
| **Upstash (Redis REST, free tier)** | Guardar en qué paso de la conversación está cada sesión (Vercel es *stateless* entre peticiones) | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` |
| **SMTP** (Gmail con contraseña de aplicación, o Brevo) | Enviar el correo con la denuncia formal | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` |
| **Vercel** | Hosting del backend | variables de entorno del proyecto |

No se necesita ningún servicio de almacenamiento de imágenes (Cloudinary/Vercel
Blob): la foto se redimensiona con Pillow y se guarda en base64 dentro del propio
estado de la sesión en Redis. Tampoco se necesita Hugging Face: la identificación de
especie la hace Gemini directamente (ver sección 9 del plan).

### 1. Gemini (Google AI Studio)
1. Entra a [aistudio.google.com](https://aistudio.google.com) y genera una API key gratuita.
2. Cópiala en `GEMINI_API_KEY`.

### 2. Upstash Redis
1. Crea una base Redis gratuita en [upstash.com](https://upstash.com).
2. En el dashboard de la base, copia la **REST URL** y el **REST Token**.
3. Pégalos en `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`.

### 3. SMTP
- **Opción rápida (Gmail):** activa verificación en 2 pasos en tu cuenta y genera una
  ["contraseña de aplicación"](https://myaccount.google.com/apppasswords). Usa
  `smtp.gmail.com`, puerto `587`, tu correo como `SMTP_USER` y la contraseña de
  aplicación como `SMTP_PASSWORD`.
- **Opción más robusta (Brevo):** crea una cuenta gratuita en
  [brevo.com](https://www.brevo.com) y usa sus credenciales SMTP (300 correos/día
  gratis, mejor entregabilidad que Gmail para envío automatizado).

### 4. Entidades destino (`app/data/entidades_car.json`)
El archivo ya trae los nombres de las 33 Corporaciones Autónomas Regionales (CAR) de
Colombia por departamento, pero **los correos están como `PENDIENTE_VERIFICAR`** —
no se inventaron direcciones reales. Antes de producción, complétalos verificando el
correo oficial de denuncias de cada entidad (sitio institucional o SIAC).

Mientras eso no esté listo, define `DEMO_OVERRIDE_EMAIL` en tu `.env`: **todas** las
denuncias se enviarán ahí en vez de a la entidad real. Si una denuncia cae en un
departamento no reconocido, se usa `DEFAULT_FALLBACK_EMAIL` como respaldo.

### 5. Vercel
1. Conecta este repositorio en [vercel.com](https://vercel.com).
2. En *Project Settings → Environment Variables*, agrega todas las variables de
   `.env.example`.
3. El entrypoint es `main.py` en la raíz del repo (`vercel.json` ya apunta ahí).
4. Si vas a exponer esta API a un frontend en otro dominio, configura
   `ALLOWED_ORIGIN` con ese dominio (o varios, separados por coma).

## Correr localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # y completa los valores
uvicorn main:app --reload
```

La API queda en `http://localhost:8000`. Probar:

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo-1", "tipo": "foto", "foto_base64": "<base64 de una foto>"}'
```

## Pruebas

```bash
pytest
```

`tests/test_state_machine.py` simula el flujo completo de una denuncia (foto →
especie → ubicación → tipo de lugar → descripción → anonimato → envío) con los
servicios externos (Gemini, geocodificación, SMTP) reemplazados por mocks, así que
corre sin credenciales reales. `tests/test_main.py` verifica que la app FastAPI
arranca y responde `/api/health`.

## Notas de diseño

- **LangChain** (`langchain-google-genai`) orquesta las llamadas a Gemini
  (identificación de especie con salida estructurada vía `with_structured_output`,
  y redacción del resumen de hechos).
- **LangGraph** (`StateGraph`) organiza la secuencia de la conversación: cada estado
  de la FSM es un nodo, con enrutamiento declarativo desde `START`. No se usa el
  checkpointer nativo de LangGraph para Redis porque depende de RediSearch, que no
  está disponible en el tier gratuito de Upstash; la persistencia real sigue siendo
  el REST de Upstash (`app/services/session_store.py`).
- Detalle completo de cada decisión, los límites de los tiers gratuitos, riesgos y
  el roadmap por fases: [docs/plan-chatweb.md](docs/plan-chatweb.md).
