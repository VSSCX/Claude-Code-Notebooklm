@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo No se encontro Python. Instala Python 3.11 o 3.12 desde python.org. & pause & exit /b 1)
if not exist .venv ( echo Creando entorno... & py -3 -m venv .venv || (pause & exit /b 1) )
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt || (echo Fallo instalacion. Revisa proxy/PyPI. & pause & exit /b 1)
if not exist .env copy .env.example .env >nul
start "" http://127.0.0.1:8000
echo Dashboard en http://127.0.0.1:8000  (NO cierres esta ventana; la cierras para detenerlo)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
