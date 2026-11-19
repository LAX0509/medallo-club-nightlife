# Nightlife Data Scientist — Backend

API REST en **FastAPI** para el control de accesos QR, listas de invitados,
comisiones de promotores y el motor de riesgos y alertas del proyecto
Nightlife Data Scientist. Implementa arquitectura limpia (Clean
Architecture) en cuatro capas: `domain`, `application`, `infrastructure`
y `api`.

## Stack

- Python 3.11+ / FastAPI
- SQLAlchemy 2.0 (ORM síncrono) + Alembic (migraciones)
- PostgreSQL (producción/desarrollo) — SQLite soportado para pruebas
- JWT (`python-jose`) + `bcrypt` para autenticación y hashing de contraseñas
- Pydantic v2 / pydantic-settings para validación y configuración
- pytest + `fastapi.testclient` para pruebas

## Arquitectura de carpetas

```
app/
├── api/v1/            # Routers HTTP, dependencias de auth/RBAC
├── application/       # Casos de uso (servicios) y el motor de riesgos
├── core/               # Configuración, seguridad (JWT/bcrypt), excepciones
├── domain/
│   ├── entities/       # Entidades de negocio (dataclasses, sin ORM)
│   └── repositories/   # Contratos (interfaces) de persistencia
├── infrastructure/
│   ├── database/       # Engine y sesión de SQLAlchemy
│   ├── models/         # Modelos ORM (SQLAlchemy)
│   └── repositories/   # Implementación de los repositorios sobre ORM
├── schemas/            # Esquemas Pydantic de entrada/salida
└── main.py             # Punto de entrada FastAPI
alembic/                 # Migraciones de base de datos
scripts/seed_data.py     # Bootstrap del primer administrador + datos demo
tests/                   # Pruebas unitarias e de integración (pytest)
```

La capa `domain` no depende de FastAPI, SQLAlchemy ni de ningún detalle de
infraestructura: los casos de uso en `application` reciben repositorios a
través de sus interfaces (`app/domain/repositories`), y `infrastructure`
provee las implementaciones concretas. Esto permite, por ejemplo,
sustituir PostgreSQL por otra base de datos sin tocar la lógica de negocio.

## Puesta en marcha

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/Mac

pip install -r requirements.txt
copy .env.example .env            # Windows (cp en Linux/Mac)
```

Editar `.env` con la cadena de conexión de PostgreSQL local. Luego:

```bash
alembic upgrade head
python -m scripts.seed_data       # crea admin/promotor/puerta de demo + 1 evento
uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`, con documentación
interactiva en `http://localhost:8000/docs` (Swagger) y
`http://localhost:8000/redoc`.

### Credenciales de demostración (creadas por `seed_data.py`)

| Rol           | Correo                              | Contraseña    |
|---------------|--------------------------------------|---------------|
| Administrador | admin@medalloclub.com                | Admin123      |
| Promotor      | promotora@medalloclub.com            | Promotor123   |
| Puerta        | puerta@medalloclub.com               | Puerta123     |

## Pruebas

```bash
pytest -q
```

Las pruebas usan una base de datos SQLite en memoria (ver
`tests/conftest.py`) y no requieren PostgreSQL. Cubren autenticación,
RBAC, el flujo completo de escaneo QR (válido / duplicado / sobreaforo),
comisiones y el motor de riesgos (`app/application/risk_engine.py`).

## Módulos funcionales (historias de usuario)

| Módulo                                   | Historia | Endpoints principales |
|-------------------------------------------|----------|------------------------|
| Autenticación y roles                     | HU003    | `POST /auth/login`, `/usuarios` |
| Control de accesos / QR                   | HU001    | `/accesos` |
| Listas de invitados y comisiones          | HU002    | `/invitados`, `/comisiones` |
| Motor de riesgos y alertas                | HU004    | `/alertas`, `/dashboard/eventos/{id}/resumen` |
| Inventario y existencias                  | —        | `/inventario` |

El administrador gestiona las fechas, temáticas y flyers desde **Agenda y flyers**. Acepta imágenes JPG, PNG, WEBP o GIF de hasta 5 MB y videos MP4 o WEBM de hasta 20 MB; el backend los sirve desde `/uploads/flyers/` y la migración `0003_eventos_agenda` agrega los campos de agenda.

### Motor de riesgos (`app/application/risk_engine.py`)

Implementa detección de anomalías con métodos estadísticos ligeros (sin
dependencias pesadas de ML), pensados como punto de extensión hacia un
modelo entrenado en el futuro:

- **Sobreaforo**: umbral dinámico según el día de la semana (los fines de
  semana toleran un margen mayor antes de alertar).
- **Cortesía duplicada**: se dispara al reutilizar un `qr_code` ya marcado
  como `usado`.
- **Comisión atípica**: z-score sobre el histórico de comisiones
  liquidadas del promotor.

## Seguridad y RBAC

- JWT con claim `rol`; cada endpoint declara los roles permitidos vía
  `require_roles(...)` (`app/api/v1/deps.py`).
- Un usuario con rol **Promotor** sólo puede ver/crear sus propias listas
  y comisiones: los routers de `invitados` y `comisiones` ignoran
  cualquier `promotor_id` que no sea el del usuario autenticado.
- Las contraseñas se hashean con `bcrypt` (nunca se devuelven por la API).
