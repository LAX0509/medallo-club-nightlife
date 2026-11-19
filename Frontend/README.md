# Nightlife Data Scientist — Frontend

Aplicación web (React + Vite) para las tres interfaces de rol definidas en
el documento de grado: **Administrador** (dashboard de riesgos, usuarios),
**Promotor** (listas de invitados y comisiones) y **Puerta** (escáner QR).

## Stack

- React 19 + Vite
- React Router (rutas protegidas por rol)
- Axios (cliente HTTP con interceptor JWT)
- `html5-qrcode` (lectura de QR con la cámara del dispositivo)
- CSS plano con tokens de diseño (`src/styles/tokens.css`), sin
  framework de UI, siguiendo la guía de estilos del documento de grado
  (negro grafito + dorado apagado, espaciado de 8px, componentes
  redondeados).

## Puesta en marcha

```bash
npm install
copy .env.example .env     # Windows (cp en Linux/Mac); ajustar VITE_API_BASE_URL si es necesario
npm run dev
```

Requiere que el backend (`../Backend`) esté corriendo en
`http://localhost:8000` (o la URL configurada en `VITE_API_BASE_URL`).

```bash
npm run build      # build de producción en dist/
npm run preview    # sirve el build de producción localmente
```

## Estructura

```
src/
├── components/   # Componentes reutilizables (layout, badges, cámara QR, KPI, alertas)
├── pages/        # Una página por pantalla del documento de grado
├── services/     # Cliente API (axios) y funciones por dominio (auth, eventos, ...)
├── store/        # Contexto de autenticación (AuthContext)
├── styles/       # Tokens de diseño y clases de componentes base
└── utils/        # Constantes (roles, rutas de inicio por rol)
```

## Pantallas (mapeadas 1:1 con el capítulo 3.4.2 del documento de grado)

| Pantalla | Ruta | Rol |
|---|---|---|
| Dashboard de riesgos y alertas | `/dashboard` | Administrador |
| Escáner de accesos QR | `/escaner` | Administrador, Puerta |
| Listas de invitados y comisiones | `/listas` | Administrador, Promotor |
| Administración de roles y usuarios | `/usuarios` | Administrador |

## Notas de implementación

- La cámara del escáner QR se degrada de forma controlada: si el
  navegador no tiene cámara disponible o el usuario no otorga permisos,
  la interfaz sigue funcionando con el campo de texto de "código QR
  manual" y el registro de cortesía manual (justificación obligatoria),
  cubriendo el escenario de baja conectividad/hardware limitado descrito
  en el documento de grado.
- El control de acceso por rol se aplica en dos capas: rutas protegidas
  en el frontend (`ProtectedRoute`, sólo UX) y autorización real en el
  backend (la fuente de verdad); un Promotor nunca recibe datos de otro
  promotor aunque manipule la URL o las peticiones.
