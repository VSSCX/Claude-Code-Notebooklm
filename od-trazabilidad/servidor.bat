@echo off
setlocal
cd /d "%~dp0"
title Order Desk - servidor
rem ============================================================================
rem  Comparte la plataforma con otras personas de la empresa desde ESTE equipo.
rem  Ellas entran con el navegador, sin instalar nada. Deja esta ventana abierta:
rem  cerrarla apaga la plataforma. Si el servidor se cae, se reinicia solo.
rem
rem  Antes de compartirla (solo la primera vez):
rem    1. Entra tu desde este equipo a http://localhost:8000 y crea la cuenta de administrador.
rem    2. En Administracion > Cuentas crea una cuenta para cada analista o KAM.
rem  Las acciones en SAP (analizar pedidos, crear entregas...) se hacen con el SAP GUI de ESTE
rem  equipo: dejalo abierto con tu sesion iniciada. Lo demas se usa desde el navegador de cada uno.
rem ============================================================================
set PUERTO=8000

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

rem Con otras personas conectadas, cada una tiene que entrar con su cuenta (si no, cualquiera en la red podria operar SAP).
if "%AUTENTICACION%"=="" set AUTENTICACION=obligatoria

rem Abre el puerto en el firewall de Windows solo para redes de dominio y privadas (la primera vez pide permisos de administrador).
netsh advfirewall firewall show rule name="Order Desk" >nul 2>nul || netsh advfirewall firewall add rule name="Order Desk" dir=in action=allow protocol=TCP localport=%PUERTO% profile=domain,private >nul 2>nul || echo [AVISO] No se pudo abrir el puerto %PUERTO% en el firewall. Ejecuta este archivo una vez como administrador, o pide a TI abrir el puerto TCP %PUERTO%.

rem Direccion IP de este equipo (la primera IPv4)
set IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do if not defined IP set IP=%%a
set IP=%IP: =%

:inicio
echo.
echo ============================================================
echo   Order Desk publicado. Comparte esta direccion:
echo     http://%COMPUTERNAME%:%PUERTO%
if defined IP echo     http://%IP%:%PUERTO%   (si el nombre no abre en otros equipos, usa esta)
echo   Tu entras desde este equipo con http://localhost:%PUERTO%
echo ============================================================
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %PUERTO% --no-access-log
echo.
echo El servidor se detuvo. Reiniciando en 10 segundos... (cierra esta ventana para apagarlo)
timeout /t 10 >nul
goto inicio
