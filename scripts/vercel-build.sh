#!/usr/bin/env bash
# Compilación en Vercel: (1) migra la base de datos, (2) copia los flyers como archivos estáticos y
# (3) compila el frontend. Variable: DATABASE_URL (obligatoria). Ya no se siembran datos de demostración en producción.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/3 Base de datos"
if [ -n "${DATABASE_URL:-}${DATABASE_URL_UNPOOLED:-}" ]; then
  PY="$(command -v python3 || command -v python || true)"
  if [ -z "$PY" ]; then
    echo "ERROR: no hay Python en el entorno de compilación para migrar la base de datos." >&2
    exit 1
  fi
  "$PY" --version
  "$PY" -m pip install --quiet --user -r requirements.txt \
    || "$PY" -m pip install --quiet --user --break-system-packages -r requirements.txt
  (
    cd Backend
    "$PY" -m alembic upgrade head
  )
else
  echo "AVISO: DATABASE_URL no está definida; se omiten las migraciones (conecta la base de datos y vuelve a desplegar)."
fi

echo "== 2/3 Flyers estáticos"
mkdir -p Frontend/public/uploads
cp -r Backend/uploads/. Frontend/public/uploads/

echo "== 3/3 Frontend"
cd Frontend
npm ci --no-audit --no-fund
npm run build
echo "Compilación terminada."
