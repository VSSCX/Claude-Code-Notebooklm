@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul || (echo No se encontro Python. Instala Python 3.11+ desde python.org o pide a TI. & pause & exit /b 1)

if not exist .venv (
  echo Creando entorno virtual...
  py -3 -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat

python -m pip install -q -r requirements.txt || (echo Fallo la instalacion de dependencias. Revisa proxy o acceso a PyPI. & pause & exit /b 1)
if not exist .env copy .env.example .env >nul
if not exist data mkdir data

alembic upgrade head || (pause & exit /b 1)

start "" http://127.0.0.1:8000
echo Plataforma en http://127.0.0.1:8000  (cierra esta ventana para detenerla)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
