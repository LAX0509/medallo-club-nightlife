@echo off
setlocal
cd /d "%~dp0"
title Medallo Club - Iniciar

echo ============================================================
echo   Medallo Club - Nightlife Data Scientist
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
  echo [X] No se encontro Python. Instala Python 3.11 o superior ^(marca "Add python to PATH"^) y vuelve a intentarlo.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [X] No se encontro Node.js. Instala Node.js 20 o superior y vuelve a intentarlo.
  pause
  exit /b 1
)

if not exist "Backend\.env" (
  copy "Backend\.env.example" "Backend\.env" >nul
  echo Se creo Backend\.env desde el ejemplo ^(sin claves de IA: el chat usara su motor local^).
)

rem --- Base de datos: PostgreSQL con Docker si esta disponible; si no, el configurado en Backend\.env
where docker >nul 2>nul
if errorlevel 1 (
  echo [i] Docker no encontrado: se usara el PostgreSQL indicado en DATABASE_URL de Backend\.env
) else (
  echo Iniciando la base de datos PostgreSQL con Docker...
  docker compose up -d --wait db
  if errorlevel 1 goto error_db
)

if not exist "Backend\.venv\Scripts\python.exe" (
  echo Preparando entorno de Python...
  python -m venv "Backend\.venv"
  if errorlevel 1 goto error
)
if not exist "Backend\.venv\.deps-installed" (
  echo Instalando dependencias del backend ^(la primera vez tarda unos minutos^)...
  "Backend\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "Backend\requirements.txt"
  if errorlevel 1 goto error
  type nul > "Backend\.venv\.deps-installed"
)

if not exist "Frontend\node_modules" (
  echo Instalando dependencias del frontend...
  pushd "Frontend"
  call npm install --no-audit --no-fund
  if errorlevel 1 goto error_pop
  popd
)

echo Aplicando migraciones de base de datos...
pushd "Backend"
call .venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 goto error_db_pop
echo Cargando datos de demostracion...
call .venv\Scripts\python.exe -m scripts.seed_demo
if errorlevel 1 goto error_db_pop
start "Medallo Club - Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload"
popd

pushd "Frontend"
start "Medallo Club - Frontend" cmd /k "npm run dev"
popd

echo.
echo ============================================================
echo   Listo. Se abrieron dos ventanas ^(backend y frontend^).
echo   Chat publico:  http://localhost:5173/reservas
echo   Panel equipo:  http://localhost:5173/login
echo   API y docs:    http://localhost:8000/docs
echo   Usuarios demo: ver README.md
echo ============================================================
timeout /t 8 >nul
start "" "http://localhost:5173/reservas"
exit /b 0

:error_db_pop
popd
:error_db
echo.
echo [X] No se pudo usar la base de datos.
echo     - Con Docker: abre Docker Desktop, espera a que diga "running" y ejecuta de nuevo este archivo.
echo     - Sin Docker: instala PostgreSQL, crea la base ^(createdb nightlife_db^) y revisa DATABASE_URL en Backend\.env.
echo     - Si el puerto 5432 esta ocupado, lee la seccion "Problemas frecuentes" del README.
pause
exit /b 1

:error_pop
popd
:error
echo.
echo [X] No se pudo preparar o iniciar la aplicacion. Revisa el mensaje anterior.
pause
exit /b 1
