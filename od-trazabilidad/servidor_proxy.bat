@echo off
rem Arranque para servidor: sin abrir el navegador y detras de un proxy inverso (HTTPS).
rem Escucha solo en 127.0.0.1; el proxy publica el puerto 443. UN solo proceso (no usar --workers).
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Falta el entorno virtual. Ver docs\SERVIDOR.md & exit /b 1)
set "PY=.venv\Scripts\python.exe"
if not exist data mkdir data
"%PY%" -m alembic upgrade head || exit /b 1
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips="127.0.0.1" --no-access-log
