@echo off
setlocal
cd /d "%~dp0"
title Dashboard D2C - servidor
rem Publica el dashboard en la red de la empresa: otros PCs entran con el navegador, sin instalar nada.
rem Deja esta ventana abierta (cerrarla apaga el dashboard). Si el servidor se cae, se reinicia solo.

where py >nul 2>nul || (echo No se encontro Python. Ejecuta primero POC_Dashboard.py para instalar. & pause & exit /b 1)
if not exist .venv\Scripts\activate.bat (echo Falta instalar. Ejecuta primero POC_Dashboard.py. & pause & exit /b 1)
call .venv\Scripts\activate.bat
if not exist .env copy .env.example .env >nul

rem Abre el puerto 8000 del firewall de Windows solo para redes de dominio y privadas (necesita permisos de administrador la primera vez).
netsh advfirewall firewall show rule name="Dashboard D2C" >nul 2>nul || netsh advfirewall firewall add rule name="Dashboard D2C" dir=in action=allow protocol=TCP localport=8000 profile=domain,private >nul 2>nul || echo [AVISO] No se pudo abrir el puerto 8000 en el firewall. Ejecuta este archivo una vez como administrador, o pidele a TI abrir el puerto TCP 8000.

:inicio
echo.
echo ============================================================
echo   Dashboard D2C publicado. Comparte esta direccion:
echo   http://%COMPUTERNAME%:8000
echo   (si el nombre no abre en otros PCs, usa la IP de este equipo en lugar del nombre)
echo ============================================================
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo El servidor se detuvo. Reiniciando en 10 segundos... (cierra esta ventana para apagarlo)
timeout /t 10 >nul
goto inicio
