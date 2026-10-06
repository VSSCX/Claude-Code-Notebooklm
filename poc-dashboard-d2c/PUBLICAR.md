# Publicar el dashboard para que otros entren sin instalarlo

**Idea:** el dashboard corre en **un solo equipo de la empresa** (que ya llega a Azure y a `clws0156`). Los demás lo abren en su
navegador con una dirección. No instalan nada y no necesitan credenciales de las bases.

```
Navegador de cada persona  ──►  http://NOMBRE-DEL-EQUIPO:8000  ──►  [equipo con el dashboard]  ──►  Azure (VTEX) + ODS (SAP)
```

Este camino es el más simple porque `clws0156` solo se alcanza desde la red de la empresa; una nube como Vercel no llega a él
(ver `VERCEL.md`).

## Paso a paso (unos 10 minutos)

1. **Elige el equipo.** Un PC o servidor de la empresa, con Windows, que quede encendido y conectado a la red (y a la VPN si las bases
   la necesitan). Idealmente no el PC personal de alguien que lo apaga o duerme.
2. **Instala o actualiza** en ese equipo: doble clic en `POC_Dashboard.py` (v3.2). Pone tus usuarios y claves de Azure y del ODS la
   primera vez; quedan solo en el `.env` de ese equipo. En un servidor conviene poner también el usuario y la clave del ODS
   (`SAP_USER` y `SAP_PASS`) en vez de usar la cuenta de Windows de quien lo abre.
3. **Quita el modo demo:** en el `.env` deja `DEMO=` vacío.
4. **Publica:** doble clic en **`servidor.bat`** (la primera vez, clic derecho → *Ejecutar como administrador*, para que abra el puerto 8000
   del firewall; si no puedes, pide a TI abrir el puerto TCP 8000 para la red interna).
   La ventana muestra la dirección para compartir, por ejemplo `http://PC-ORDERDESK:8000`. **Déjala abierta**: si se cierra, se apaga.
5. **Comparte la dirección** (o guárdala como favorito en cada navegador). Si el nombre no abre en otro PC, usa la IP del equipo
   (`ipconfig` en el equipo) en vez del nombre: `http://10.x.x.x:8000`.

Probado: la aplicación responde por la interfaz de red (`0.0.0.0`) y 200 consultas simultáneas de actualización se atienden en menos
de 1 segundo; 25 personas cargando el tablero **exactamente a la vez** tardan hasta ~5 s la primera carga (con los datos de ejemplo).
Para 10 a 20 personas del Order Desk, que filtran en momentos distintos, no debería notarse. No se probó contra las bases reales.

## Que no se apague (recomendado)

- **Energía:** en el equipo, `powercfg /change standby-timeout-ac 0` (que no se suspenda enchufado).
- **Reinicio automático si Windows se reinicia:** el programador de tareas, que abre `servidor.bat` al iniciar sesión o con el equipo:
  `schtasks /create /tn "Dashboard D2C" /tr "C:\ruta\dashboard-d2c\servidor.bat" /sc onlogon`
  (si lo pones al arrancar el equipo sin sesión, usa un usuario con acceso al ODS y completa `SAP_USER`/`SAP_PASS`).
- **Actualizaciones:** detén `servidor.bat`, ejecuta la nueva `POC_Dashboard.py` (conserva el `.env`) y vuelve a abrir `servidor.bat`.

## Lo que hay que saber

- **Un solo proceso, una sola consulta a las bases:** el servidor revisa cambios cada 10 s y todos los usuarios ven los mismos datos al
  mismo tiempo. Más usuarios no multiplican la carga sobre Azure ni el ODS. No lo inicies con varios *workers*.
- **Sin clave (como pediste):** cualquiera que llegue a la dirección ve los pedidos. Funciona bien en la red interna; no lo expongas a
  Internet. Si más adelante quieres usuario y clave, es un cambio pequeño (autenticación básica en el servidor).
- **HTTP, no HTTPS:** el tráfico dentro de la red no va cifrado. Para una intranet suele bastar; si TI lo exige, se pone un proxy con
  certificado delante.
- **Asistente de consultas (icono de chat):** responde con reglas, sin IA ni internet. Si quieres una IA (local con Ollama, por ejemplo), ver `ASISTENTE.md`. Como el resto del tablero no tiene clave: cualquiera en la red puede preguntar; con una IA externa, el texto de las preguntas sale de tu red.
- **Las notificaciones de la campana** (pedidos nuevos) se guardan en el navegador de cada persona: cada uno ve las suyas.
- **Si el otro PC se queda en «Loading…» (pantalla gris, nunca carga):** casi siempre es el firewall de Windows del equipo servidor,
  que descarta la conexión sin responder. Causas típicas: la red del equipo está marcada como *Public* (la regla de `servidor.bat` es solo
  para redes de dominio y privadas), o Windows creó una regla que **bloquea python.exe** cuando apareció el aviso del firewall y se canceló.
  Ejecuta `diagnostico.bat` en el equipo servidor: muestra el perfil de red, la regla y los bloqueos. Desde el otro PC, en PowerShell:
  `Test-NetConnection NOMBRE-O-IP -Port 8000` (`TcpTestSucceeded : False` = lo bloquea el firewall o la red; `True` = revisa el proxy del navegador).
  Prueba también con la IP en vez del nombre.
- **Si algo no abre:** (1) ¿está abierta la ventana de `servidor.bat`? (2) ¿el firewall deja pasar el puerto 8000? (3) ¿el otro PC está
  en la misma red o en la VPN? (4) ¿en el equipo se ve `http://localhost:8000`? Si no se ve ahí, el problema es el `.env` o el driver ODBC.
- Pide a TI el visto bueno: se publican datos de pedidos a toda la red interna.

## Otras opciones (más complejas)

| Opción | Cuándo conviene | Qué exige |
|---|---|---|
| Máquina virtual en la nube (Azure) | Gente fuera de la oficina sin VPN | VPN o conexión privada hacia `clws0156`, costo mensual, TI |
| Túnel seguro (por ejemplo Cloudflare Tunnel con Access) sobre el mismo equipo | Entrar desde Internet sin abrir puertos | Cuenta del servicio, login por persona y aprobación de TI |
| Vercel | Solo para el modo demo | Copiar los datos a una base en Internet (ver `VERCEL.md`) |
