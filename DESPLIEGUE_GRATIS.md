# Despliegue gratuito con buena disponibilidad

Objetivo: tener Medallo Club en internet **sin pagar**, estable para la sustentación y para que el jurado
y compañeros lo prueben desde su celular (incluida la cámara del escáner, que exige https).

> **Estado:** esto es la estrategia y la guía; el despliegue todavía **no se ha ejecutado**. Los planes
> gratuitos cambian: confirma los límites en la página de cada proveedor antes de crear las cuentas.
> Lo que está marcado como *no verificado* no pude comprobarlo.

## Arquitectura recomendada

```
 Navegador ──► Frontend estático (Cloudflare Pages o Vercel)  ── CDN global, nunca se duerme
      │
      └──────► Backend FastAPI (Render, plan Free) ──► PostgreSQL (Neon, plan Free)
                       │                                  
                       ├──► Gemini (3 claves) → Groq → motor local   (IA, ya implementado)
                       └──► WhatsApp Cloud API (webhook entra por la URL pública del backend)
```

| Pieza | Servicio | Por qué | Límites a tener en cuenta (verificados en sus docs, oct-2026) |
|---|---|---|---|
| Frontend (React/Vite) | **Cloudflare Pages** (o Vercel) | Estático, CDN, https automático, sin dormirse | Build con `npm run build`, carpeta `dist` |
| Backend (FastAPI) | **Render – Web Service Free** | Único plan gratis cómodo para un servicio Python persistente; despliega desde GitHub | Se **duerme tras 15 min sin tráfico**; despertar tarda ~15–60 s. 750 h gratis/mes por workspace. El disco es **efímero** |
| Base de datos | **Neon – Free** | PostgreSQL real (el proyecto usa PostgreSQL), arranque en <1 s tras suspensión | 0,5 GB y 100 CU-h/mes por proyecto; se suspende tras 5 min inactivo |
| IA | Gemini + Groq (ya configurados) | Gratis, con rotación de claves y modelos | Cuotas diarias por modelo/proyecto |

Costo total: **$0**. Render, Neon, Cloudflare y Vercel no piden tarjeta en el plan gratuito, según sus páginas;
*confirma al registrarte*.

## El punto débil y cómo manejarlo: el backend se duerme

Es la única parte de esta combinación que afecta la disponibilidad. Opciones, de más a menos recomendable:

1. **Calentar antes de cada demostración** (recomendado, gratis y dentro de las reglas): 3 minutos antes
   de exponer, abre `https://<tu-backend>.onrender.com/health` y espera la respuesta; después de eso responde
   en milisegundos durante toda la sesión. Haz lo mismo antes de que un jurado pruebe el sistema.
2. **Mensaje de «despertando servidor» en el frontend:** si la primera petición tarda, mostrar un aviso de
   «Despertando el servidor (~30 s)…» en vez de un error. (Pendiente de implementar; es un cambio pequeño.)
3. **Ping periódico (UptimeRobot, cron-job.org) cada 10–14 min:** mantiene despierto el servicio y entra en
   las 750 h/mes (un mes tiene ~744 h). **Ojo:** personal de Render ha dicho en su foro que mantenerlo
   despierto a propósito va contra el espíritu del plan gratuito y que un uso masivo podría hacer que
   retiren el plan; úsalo solo durante la ventana de evaluación, no como práctica permanente.
4. **Alternativa realmente «siempre encendida» (requiere tarjeta para verificar la cuenta):** una máquina
   virtual *Always Free* de Oracle Cloud con Docker (backend + PostgreSQL + Caddy para https). No se duerme y
   da la mejor disponibilidad gratuita, pero exige más administración y suele tener problemas de cupo por
   región. *No pude verificar los límites actuales de Oracle ni de Koyeb; revísalos antes de decidir.*
   Google Cloud Run también tiene capa gratuita generosa (escala a cero, arranque de 2–5 s) pero requiere
   tarjeta.

**Recomendación:** plan 1 + 2 para la sustentación; si el proyecto va a vivir meses con visitas reales,
migrar el backend a la VM de Oracle (opción 4).

## Pasos (≈ 45 minutos)

### 1) Código en GitHub
Crea un repositorio privado y sube la carpeta **sin** `Backend/.env` (ya está en `.gitignore`) ni
`node_modules`/`.venv`. Los secretos se cargan como variables de entorno en cada servicio.

### 2) Base de datos en Neon
1. Crea cuenta en neon.com → *New project* (región cercana, p. ej. `aws-us-east-1`).
2. Copia la cadena de conexión y conviértela al formato del proyecto:
   `postgresql+psycopg2://USUARIO:CLAVE@HOST/neondb?sslmode=require`.

### 3) Backend en Render
1. *New → Web Service* → conecta el repositorio → **Root Directory:** `Backend`.
2. **Runtime:** Python 3.11 (variable `PYTHON_VERSION=3.11.9`).
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `alembic upgrade head && python -m scripts.seed_demo && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (el `seed_demo` es idempotente; quítalo cuando quieras empezar con datos reales).
5. **Health Check Path:** `/health`
6. **Variables de entorno:**

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | cadena de Neon del paso 2 |
   | `JWT_SECRET_KEY` | un texto aleatorio largo (≥ 48 caracteres) |
   | `ENVIRONMENT` | `production` |
   | `CORS_ORIGINS` | `["https://<tu-frontend>.pages.dev"]` (JSON) |
   | `PUBLIC_FRONTEND_URL` | `https://<tu-frontend>.pages.dev` |
   | `GEMINI_API_KEY`, `GEMINI_API_KEYS_EXTRA`, `GROQ_API_KEY` | tus claves |
   | `WHATSAPP_*` | opcional, ver README |

### 4) Frontend en Cloudflare Pages (o Vercel)
1. *Create project* → conecta el repositorio → **Root directory:** `Frontend`.
2. **Build command:** `npm run build` · **Output:** `dist`.
3. **Variable:** `VITE_API_BASE_URL` = `https://<tu-backend>.onrender.com/api/v1` (se fija al compilar).
4. Las rutas del frontend (`/reservas`, `/login`, `/pase/...`) requieren redirigir todo a `index.html`: el
   proyecto ya incluye `Frontend/public/_redirects` (Cloudflare/Netlify) y `Frontend/vercel.json` (Vercel).

### 5) Comprobar
`https://<backend>/health` → `{"status":"ok"}`; abrir el frontend, entrar como admin y hacer una reserva
por el chat. Para la cámara del escáner usa siempre la URL https.

### 6) WhatsApp (opcional)
Con el backend en una URL https pública: en Meta → WhatsApp → Configuración → Webhook, URL
`https://<backend>/webhooks/whatsapp` y el mismo `WHATSAPP_WEBHOOK_VERIFY_TOKEN`; suscribe el campo `messages`.
Calienta el backend antes de probar: si está dormido, Meta reintenta, pero la primera entrega puede fallar.

## Pendientes conocidos antes de desplegar de verdad

| Tema | Detalle | Solución propuesta |
|---|---|---|
| **Flyers subidos** | Se guardan en `Backend/uploads/` (disco). En Render Free el disco se borra al dormir/redesplegar | Guardar los flyers en un servicio gratuito de imágenes (p. ej. Cloudinary) o dejar flyers fijos de demostración dentro del repo |
| Aviso de «servidor despertando» | Hoy una petición lenta se ve como carga larga | Mensaje en el frontend (cambio pequeño) |
| Límites de Neon | 0,5 GB: sobra para una demo; los registros de chat crecen con el uso | Purga periódica de conversaciones antiguas si se usa mucho |
| `seed_demo` en producción | Carga datos ficticios y usuarios demo con contraseñas conocidas | Quitar del comando de inicio y cambiar contraseñas antes de abrir al público |
| Contraseñas demo | `Admin123`, etc. | Cambiarlas desde *Equipo* tras el primer ingreso |

## Alternativas si Render deja de ser gratuito
- **Backend:** Koyeb, Fly.io, Railway (créditos de prueba) o la VM de Oracle. *No verificados.*
- **Base de datos:** Supabase (PostgreSQL gratis; se pausa tras 7 días de inactividad, *no verificado*) o
  PostgreSQL dentro de la misma VM.

---

## Si todo corre en Vercel (frontend + API en el mismo dominio, como `night-life-med.vercel.app`)

Vercel ejecuta la API como funciones *serverless*. Eso cambia cuatro cosas respecto a un servidor normal:

| Tema | Qué pasa en Vercel | Qué hace el proyecto / qué debes hacer |
|---|---|---|
| **Avisos de WhatsApp** | La función se congela al enviar la respuesta: las tareas «en segundo plano» pueden no ejecutarse nunca (los avisos «no llegan») | Ya resuelto: en Vercel (`VERCEL=1`) el aviso se envía **antes** de responder (`app/core/tareas.py`). Se puede forzar con `NOTIFICACIONES_EN_LINEA=true` |
| **Rutas del frontend** (`/reservas`, `/login`, `/pase/...`) | Abrirlas directo (enlaces compartidos, QR, recargar) da **404** si falta la regla de reescritura | Añade al `vercel.json` la regla de abajo, **al final** de `rewrites` |
| **Variables de entorno** | Cambiarlas no afecta al despliegue ya publicado | Después de editar *Settings → Environment Variables* haz **Redeploy** |
| **Disco** | Solo lectura: no se pueden subir flyers desde el panel (la API responde 503 con un mensaje claro) | Sube los flyers al repositorio (`Backend/uploads/flyers`) o usa almacenamiento externo (Cloudinary) |

Regla de reescritura para las rutas del frontend (ponla después de las reglas que envían `/api`, `/health`,
`/docs`, `/openapi.json`, `/webhooks` y `/uploads` a la función de FastAPI):

```json
{ "source": "/((?!api/|health|docs|openapi.json|webhooks/|uploads/|assets/|favicon.svg).*)", "destination": "/index.html" }
```

**Variables mínimas para los avisos de WhatsApp:** `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`
(token permanente de usuario del sistema), `WHATSAPP_TEMPLATE_NAME`, `WHATSAPP_TEMPLATE_LANGUAGE` (**el
mismo idioma con que Meta aprobó la plantilla**, p. ej. `es`, no `es_CO`) y `WHATSAPP_NOTIFY_TO` (con
indicativo, p. ej. `573001234567`).

**Diagnóstico sin mirar logs:** entra al panel como administrador → *Asistente y WhatsApp* →
**Diagnosticar aviso de reservas**. Revisa variables, token, número y envía el aviso real con datos de
prueba; si algo falla, muestra el paso y el error exacto de Meta.
