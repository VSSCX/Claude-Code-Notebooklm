@echo off
setlocal
title Dashboard D2C - diagnostico de red
echo ============================================================
echo   Diagnostico: por que otros PCs no abren el dashboard
echo   Ejecuta este archivo EN EL EQUIPO DONDE CORRE servidor.bat
echo   (con servidor.bat abierto en otra ventana)
echo ============================================================
echo.
echo [1] Responde el dashboard en este mismo equipo?
curl.exe -s -m 10 -o NUL -w "    http://localhost:8000  ->  HTTP %%{http_code}  (200 = bien, 000 = el servidor no esta corriendo)\n" http://localhost:8000/
echo.
echo [2] Esta escuchando para toda la red (0.0.0.0:8000)?
netstat -an | findstr ":8000" | findstr LISTENING
echo     (debe aparecer 0.0.0.0:8000; si solo dice 127.0.0.1:8000, se abrio run.bat en vez de servidor.bat)
echo.
echo [3] Direcciones IP de este equipo (prueba http://IP:8000 desde el otro PC)
ipconfig | findstr /i "IPv4"
echo.
echo [4] Perfil de la red (Public = el firewall bloquea la regla del dashboard)
powershell -NoProfile -Command "Get-NetConnectionProfile | Select-Object Name,NetworkCategory | Format-Table -AutoSize"
echo [5] Regla de firewall del dashboard
netsh advfirewall firewall show rule name="Dashboard D2C" | findstr /i "Enabled Profiles Action LocalPort"
echo.
echo [6] Reglas de Windows que BLOQUEAN python (anulan la regla anterior)
powershell -NoProfile -Command "Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True | Where-Object { ($_ | Get-NetFirewallApplicationFilter).Program -like '*python*' } | Select-Object DisplayName,Profile | Format-Table -AutoSize"
echo.
echo ------------------------------------------------------------
echo   Desde el OTRO PC, en PowerShell, ejecuta:
echo     Test-NetConnection NOMBRE-O-IP-DE-ESTE-EQUIPO -Port 8000
echo   TcpTestSucceeded : True  -> la red llega; el problema es el navegador o un proxy
echo   TcpTestSucceeded : False -> lo bloquea el firewall o la red (revisa los pasos 4, 5 y 6)
echo ------------------------------------------------------------
pause
