# Medallo Club — Nightlife Data Scientist

Plataforma de gestión de accesos, promotores, reservas e inventario para el entretenimiento
nocturno, con un asistente conversacional de IA y analítica de sentimientos en tiempo real.
Trabajo de grado — Ingeniería de Sistemas, Universidad Católica Luis Amigó (2026).
Autores: Juan Camilo Nieto Arboleda y Manuel Alejandro Hernández Lizcano.

**Demo en producción:** https://medallo-club.vercel.app

| | |
|---|---|
| **Backend** | FastAPI, SQLAlchemy, Alembic, PostgreSQL (Neon), JWT con 3 roles |
| **Frontend** | React + Vite (SPA) |
| **IA** | Asistente de reservas y análisis de sentimientos con cadena de respaldo Gemini → Groq → motor local |
| **Integraciones** | WhatsApp Cloud API (plantillas, webhooks, estados de entrega), QR de acceso |
| **Calidad** | 393 pruebas automatizadas, 99 % de cobertura del backend |
| **Despliegue** | Vercel (serverless) + Neon, migraciones automáticas en el build |

## Inicio rápido (Windows, ~5 minutos la primera vez)

**Requisitos:** Python 3.11+, Node.js 20+ y Docker Desktop (para la base de datos; si no lo tienes, ver
«Sin Docker» más abajo).

1. Clona el repositorio y abre **Docker Desktop** (espera a que diga *running*).
2. Haz doble clic en **`INICIAR_MEDALLO.bat`**. Crea el entorno, instala dependencias, levanta PostgreSQL,
   aplica las migraciones, carga datos de demostración y abre el backend, el frontend y el navegador.
3. Entra a **http://localhost:5173/reservas** (chat público) o a **http://localhost:5173/login** (equipo).

| Rol | Correo | Contraseña | Qué ve |
|---|---|---|---|
| Administrador | admin@medalloclub.com | Admin123 | Todo: panel, reservas, inventario, sentimientos, asistente, equipo |
| Promotor | promotora@medalloclub.com | Promotor123 | Sus invitados, reservas referidas, comisiones y eventos |
| Puerta | puerta@medalloclub.com | Puerta123 | Escáner QR, búsqueda de invitados e historial |

### Manual (Mac/Linux o sin el .bat)

```bash
docker compose up -d --wait db           # PostgreSQL en el puerto 5432 (usuario/clave postgres)
cd Backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head                      # crea las tablas
python -m scripts.seed_demo               # datos de demostración
uvicorn app.main:app --reload             # API en http://localhost:8000/docs

cd ../Frontend                            # en otra terminal
npm install && npm run dev                # http://localhost:5173
```

**Sin Docker:** instala PostgreSQL 14+, crea la base (`createdb nightlife_db`) y ajusta `DATABASE_URL`
en `Backend/.env` (formato `postgresql+psycopg2://usuario:clave@localhost:5432/nightlife_db`).

## Guía de prueba sugerida (≈15 minutos)

1. **Chat público** (`/reservas`): escribe *«quiero reservar un palco para 6 personas»*, elige evento,
   da nombre y teléfono y confirma. Prueba también una queja (*«el servicio fue pésimo, quiero hablar con
   alguien»*) y una pregunta abierta (*«hay descuento para grupos?»*).
2. **Admin → Solicitudes de reserva:** *Confirmar* la solicitud (ubicación, hora límite, consumo mínimo) →
   se emite el código `MC-…` y un pase QR por asistente. Abre **Ver pases** y un pase público.
3. **Cliente:** abre el enlace de gestión que entrega el chat (`/reservas?reserva=…&token=…`): código de
   garantía, pases y cancelación.
4. **Puerta** (o Admin → Control de acceso): valida un pase pegando el código o el enlace; vuelve a validar
   el mismo → se rechaza como duplicado. Registra una cortesía manual con justificación.
5. **Inventario:** registra un consumo que deje un producto bajo su mínimo → aparece la alerta en la campana.
6. **Sentimientos:** revisa el panel, las conversaciones escaladas y el *Probador de análisis*.
7. **Asistente y WhatsApp:** estado de conexiones, *Probar conexión con la IA* y el probador del asistente.
8. **Panel general:** *Informe de la jornada* (redactado con IA).
9. **Promotor** y **Puerta:** inicia sesión con cada rol y comprueba que solo ve lo suyo.

## Qué incluye

| Módulo | Descripción |
|---|---|
| Control de accesos | Escáner QR con cámara, validación anti-reuso (segura bajo concurrencia entre puertas), cortesías manuales justificadas, incidencias |
| Formatos de QR | Lee código, enlace, `medallo://`, JSON, base64 y texto; genera QR (PNG/SVG); pase digital público con calendario (.ics) |
| Listas y comisiones | Invitados por promotor, comisiones y liquidación |
| Roles | Administrador, Promotor y Puerta con JWT |
| Riesgos | Alertas de sobreaforo, cortesía duplicada y comisión atípica; informe de jornada con IA |
| Reserva garantizada | Solicitud → confirmación con código `MC-…`, cupo asegurado, ubicación, hora límite, consumo mínimo y un pase QR por asistente; vista privada del cliente |
| Asistente de IA | Chat web y WhatsApp: reservas conversacionales, preguntas frecuentes, escalamiento a una persona |
| Sentimientos | Polaridad, emoción, aspectos (servicio, precio, música…) y urgencia; panel analítico y conversaciones |
| Inventario | Existencias, movimientos trazables, costos, consumo por evento, exportación CSV |
| Notificaciones | Campana interna (stock, reservas, riesgos, clientes molestos) + WhatsApp opcional |

## IA y WhatsApp

- **IA.** El asistente usa **Google Gemini** (varias claves gratuitas de proyectos distintos, con modelos de
  respaldo) y, si Gemini falla o se agota, **Groq** (también gratis); si todo falla, sigue con su **motor local
  de reglas**, así que el chat nunca se cae. Las claves se leen de `Backend/.env`
  (`GEMINI_API_KEY`, `GEMINI_API_KEYS_EXTRA`, `GROQ_API_KEY`; ver `Backend/.env.example`). El panel
  *Asistente y WhatsApp* muestra qué proveedores están activos.
  Las claves gratuitas tienen cuotas diarias por modelo y por proyecto; el asistente ahorra consultas
  (los pasos guiados de una reserva usan reglas locales y solo consulta a la IA en mensajes abiertos o con
  tono negativo). Claves nuevas: <https://aistudio.google.com/apikey> y <https://console.groq.com/keys>.
- **WhatsApp.** Este paquete trae configurado el **aviso interno de nueva reserva**: token permanente,
  Phone Number ID, plantilla aprobada `medallo_nueva_reserva` (idioma `es`) y el destino `WHATSAPP_NOTIFY_TO`.
  **Ojo:** cada vez que se cree una reserva (por el chat o el formulario) se envía un WhatsApp **real** a ese
  número. Para probar sin enviar mensajes, deja vacío `WHATSAPP_ACCESS_TOKEN` en `Backend/.env`. Con el
  número de prueba de Meta, el destino debe estar agregado como destinatario en el panel de Meta.
  Pendientes opcionales: plantilla de confirmación al cliente y de inventario (sin ellas, esos avisos solo
  llegan a la campana del panel) y el bot por WhatsApp, que además necesita el webhook (URL pública con https,
  `WHATSAPP_APP_SECRET` y `WHATSAPP_WEBHOOK_VERIFY_TOKEN`); el chat web no lo necesita.
- **Seguridad.** `Backend/.env` contiene claves y el token de WhatsApp: no lo subas a git ni lo compartas por
  canales públicos.

## Pruebas y validación

```bash
cd Backend
pytest -q                                          # 141 pruebas (SQLite en memoria; sin red)
python -m scripts.prueba_concurrencia              # carrera del mismo QR + carga (backend en marcha)
python -m scripts.generar_reporte_validacion --ejecutar
```

El reporte de validación (Word) está en `Reporte de validacion/`.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| «port is already allocated» / el puerto 5432 está ocupado (ya tienes otro PostgreSQL) | `set DB_PORT=5433` (Windows) o `DB_PORT=5433` (Mac/Linux) antes de `docker compose up -d --wait db`, y cambia `:5432/` por `:5433/` en `DATABASE_URL` de `Backend/.env` |
| `password authentication failed` | Estás apuntando a otro PostgreSQL: usa el de Docker (`postgres`/`postgres`) o corrige `DATABASE_URL` |
| El .bat dice que no pudo usar la base de datos | Abre Docker Desktop y espera a que esté en *running* |
| La cámara del escáner no abre | Los navegadores solo permiten cámara en `localhost`/https y con permiso; usa el campo «Ingresa el código» |
| El chat responde sin «IA» | Faltan claves o se agotó la cuota diaria: el motor local sigue funcionando; revisa el panel *Asistente y WhatsApp* |
| Error de CORS al abrir el frontend desde otra dirección | Usa `http://localhost:5173` (no `127.0.0.1`) o añade el origen a `CORS_ORIGINS` |

## Estructura

- `Backend/` — FastAPI con arquitectura limpia (`domain`, `application`, `infrastructure`, `api`), Alembic (migraciones 0001–0014) y pruebas.
- `Frontend/` — React + Vite (público: chat, reserva y pase; equipo: panel, escáner, reservas, inventario, sentimientos, asistente).
- `Database/` — `schema.sql` (generado con pg_dump desde las migraciones) y semillas SQL.
- `Reporte de validacion/` — reporte de validación y evidencia de concurrencia.
- `docker-compose.yml` — PostgreSQL local.
- `DESPLIEGUE_GRATIS.md` — estrategia de despliegue gratuito con buena disponibilidad.
