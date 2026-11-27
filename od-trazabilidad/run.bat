@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul || (echo No se encontro Python. Instala Python 3.11+ desde python.org o pide a TI. & pause & exit /b 1)

set "PY=.venv\Scripts\python.exe"
rem Un entorno virtual a medias o copiado de otro equipo no sirve: se recrea.
if exist "%PY%" ("%PY%" -c "import sys" >nul 2>nul || rmdir /s /q .venv)
if not exist "%PY%" (
  if exist .venv rmdir /s /q .venv
  echo Creando entorno virtual. Puede tardar un minuto...
  py -3 -m venv .venv || (pause & exit /b 1)
)
if not exist "%PY%" (echo No se pudo crear el entorno virtual en .venv. Avisa a TI. & pause & exit /b 1)

echo Instalando dependencias. La primera vez tarda unos minutos, no cierres esta ventana...
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt || (echo Fallo la instalacion de dependencias. Revisa proxy o acceso a PyPI. & pause & exit /b 1)
if not exist .env copy .env.example .env >nul
if not exist data mkdir data

echo Preparando la base de datos...
"%PY%" -m alembic upgrade head || (echo Fallo la creacion de la base de datos. & pause & exit /b 1)

start "" http://127.0.0.1:8000
echo Plataforma en http://127.0.0.1:8000  (cierra esta ventana para detenerla)
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
