# Order Desk en un servidor: especificaciones para TI

Documento para quien va a alojar la plataforma. Resume qué se necesita, cómo se instala y cómo se vigila.
Todo lo que está aquí funciona hoy; lo que no, está marcado como **pendiente**.

## 1. En una página

| Tema | Valor |
|---|---|
| Qué es | Una aplicación web (Python 3.11 + FastAPI) con base de datos y archivos locales. No necesita Docker ni Node. |
| Usuarios | Un equipo pequeño de analistas (decenas, no cientos). Cada uno entra con su usuario y clave. |
| Servidor recomendado | VM Windows Server 2019/2022, **2 vCPU, 4 GB RAM, 40 GB de disco**. Linux también sirve para todo menos SAP GUI (ver §6). |
| Procesos | **Un solo proceso** de la aplicación (no usar varios *workers*): la cola de trabajos de SAP y el bloqueo de intentos viven en memoria. |
| Puerto | La aplicación escucha en `127.0.0.1:8000`. Un proxy inverso (IIS, nginx o Caddy) publica `443`. |
| Base de datos | SQLite (cabe para un equipo chico) **o** SQL Server vía `DATABASE_URL` (recomendado si más de ~5 analistas trabajan a la vez). |
| Acceso saliente | SQL Server de las bases (solo lectura) y las carpetas de red con la Base de Medidas y la maestra de homologación. |
| Internet | No se necesita en funcionamiento. Solo en la instalación (PyPI) o con un espejo interno. |

## 2. Qué pedirle a TI

1. **VM** con las medidas de la tabla.
2. **Nombre DNS interno**, por ejemplo `orderdesk.empresa.cl`, y un **certificado HTTPS** de la CA interna.
3. **Cuenta de servicio** (por ejemplo `svc-orderdesk`) con:
   - lectura sobre las carpetas de red de la Base de Medidas y la maestra de homologación;
   - lectura sobre las bases de SQL Server (plan de ventas y saldos) o su propio usuario SQL de solo lectura;
   - escritura sobre la carpeta de la aplicación (`data\`, `logs`).
4. **Regla de firewall**: 443/TCP desde la red de los analistas hacia la VM. El puerto 8000 queda cerrado hacia fuera.
5. **Python 3.11 o superior** y, si se usa SQL Server, el **ODBC Driver 17 o 18**.
6. Si se usa SQL Server para la plataforma: una **base vacía** (`Trazabilidad`) y un login con permisos de crear tablas la primera vez (después puede bajarse a lectura/escritura).
7. Una **copia de seguridad** diaria de la base y de la carpeta `data\archivos` (ver §7).

## 3. Instalación

```bat
:: 1. Copiar la carpeta od-trazabilidad a D:\OrderDesk (o usar el instalador crear_proyecto.py)
cd D:\OrderDesk
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

:: 2. Configuración: copiar .env.example a .env y completar (ver §4)
copy .env.example .env
notepad .env

:: 3. Crear/actualizar las tablas
.venv\Scripts\alembic upgrade head

:: 4. Probar a mano
servidor.bat
```

`servidor.bat` levanta la aplicación en `127.0.0.1:8000` **sin abrir el navegador**, con los encabezados del proxy
(`--proxy-headers`) para que el registro guarde la IP real de cada analista.

### Dejarla como servicio de Windows (arranca sola y se reinicia si cae)

Con [NSSM](https://nssm.cc) (o el Programador de tareas):

```bat
nssm install OrderDesk D:\OrderDesk\servidor.bat
nssm set OrderDesk AppDirectory D:\OrderDesk
nssm set OrderDesk ObjectName EMPRESA\svc-orderdesk *clave*
nssm set OrderDesk AppStdout D:\OrderDesk\data\logs\servicio.out.log
nssm set OrderDesk AppStderr D:\OrderDesk\data\logs\servicio.err.log
nssm set OrderDesk AppExit Default Restart
nssm start OrderDesk
```

### Proxy inverso (ejemplo con Caddy; en IIS es *URL Rewrite + ARR*)

```
orderdesk.empresa.cl {
    tls /ruta/certificado.pem /ruta/llave.pem
    reverse_proxy 127.0.0.1:8000
}
```

Cuando el acceso es por HTTPS, poner `COOKIE_SEGURA=1` en el `.env`.

## 4. Configuración (`.env`)

| Variable | Para qué | Valor de producción |
|---|---|---|
| `DATABASE_URL` | Base de la plataforma | `mssql+pyodbc://usuario:clave@SERVIDOR/Trazabilidad?driver=ODBC+Driver+17+for+SQL+Server` (o dejar SQLite) |
| `BASES_URL` | SQL Server de las bases (solo lectura) | cadena con `trusted_connection=yes` si corre con la cuenta de servicio |
| `ADMIN_INICIAL` | Primer administrador (`usuario:clave:Nombre`) | Solo para el primer arranque; después **borrar la línea** |
| `AUTENTICACION` | `obligatoria` fuerza entrar aunque no haya cuentas | `obligatoria` |
| `COOKIE_SEGURA` | La sesión solo viaja por HTTPS | `1` |
| `SESION_HORAS` | Horas sin uso tras las que se pide entrar otra vez | `10` |
| `RETENCION_ACTIVIDAD_DIAS` | Cuánto se guarda el historial de actividad | `365` |
| `RETENCION_ERRORES_DIAS` | Cuánto se guardan los errores ya resueltos | `120` |
| `LOGS_DIR` | Carpeta del log en archivo | `D:\OrderDesk\logs` |
| `VISORES_DIR` | Visores 3D generados | volumen persistente |
| `BASE_MEDIDAS`, `MAESTRA_HOMOLOGACION`, `VISOR_ASSETS` | Rutas de red | las reales de la empresa |

## 5. Cuentas y seguridad

- **Una cuenta por analista.** El primer administrador se crea con `ADMIN_INICIAL` (o desde el propio servidor, en la pantalla de entrada). Después el administrador crea las demás en *Administración → Cuentas*.
- La clave temporal se muestra **una sola vez**; la persona debe cambiarla al entrar. Mínimo 8 caracteres, con letras y números, sin su usuario dentro.
- Las claves se guardan con **PBKDF2-SHA256 (240.000 iteraciones)** y sal propia. Nunca en claro.
- La sesión es una cookie `od_sesion` (`HttpOnly`, `SameSite=Lax`, `Secure` con HTTPS). En la base solo queda la huella (SHA-256) del identificador, no el identificador.
- La sesión se cierra tras `SESION_HORAS` sin uso, al cerrar sesión o si el administrador desactiva la cuenta o restablece su clave.
- **5 intentos fallidos** seguidos de un mismo usuario desde una misma IP bloquean el ingreso 5 minutos.
- Toda llamada que modifica datos exige la cabecera `X-Requested-With: od` (defensa contra peticiones de otros sitios).
- Siempre queda al menos un administrador activo; nadie puede desactivarse a sí mismo.
- **Pendiente** (si TI lo pide): ingreso con la cuenta corporativa (Microsoft Entra ID / ADFS) en lugar de usuario y clave propios.

## 6. SAP GUI

Las acciones que escriben en SAP (crear entregas, grupos, citas, borrar) usan **SAP GUI Scripting**. Eso exige una
**sesión de escritorio Windows con SAP GUI abierto y con la sesión iniciada**, algo que un servicio sin pantalla no tiene.
Opciones, de más simple a más robusta:

1. **El servidor es un Windows con sesión de escritorio** donde una persona (o un usuario técnico) deja SAP GUI abierto. Sirve para pocos analistas, pero SAP procesa de a una acción a la vez (la plataforma ya las pone en cola).
2. **Agente en el PC del analista** *(pendiente de construir)*: un programa pequeño que corre en su PC, usa su SAP GUI y recibe las órdenes de la plataforma. Es lo recomendable para varios analistas, porque cada uno actúa con su propio usuario SAP.
3. **Lectura de SAP por RFC/OData** *(requiere a Basis)*: reemplaza al scripting y no necesita GUI.

Mientras no esté el agente, las acciones de SAP se hacen donde corre el servidor. Todo lo demás (pedidos, análisis con las bases, cubicaje, visor 3D, exportes) funciona desde el navegador de cada analista sin instalar nada.

## 7. Datos, respaldos y registro

| Qué | Dónde | Respaldo |
|---|---|---|
| Base SQLite | `data\trazabilidad.db` | La plataforma hace una copia diaria sola en `data\respaldos` (guarda las últimas). Copiar esa carpeta fuera del servidor. |
| Base en SQL Server | la base `Trazabilidad` | El respaldo normal de SQL Server. |
| Archivos subidos (PDF, etc.) | `data\archivos` | Copia de carpeta. |
| Visores 3D | `data\visores` | No hace falta: se regeneran. |
| Log en archivo | `LOGS_DIR\od.log` | Rota solo: 5 MB × 8 archivos. |

## 8. Cómo se sigue un problema

1. **Código de seguimiento.** Cada petición recibe un código (cabecera `X-Request-ID`). Si falla, el analista ve el mensaje con su código, por ejemplo *«Error interno. Código de seguimiento: 3f9a1c0b7d»*.
2. **Administración → Errores.** Los errores iguales se agrupan: primera y última vez, cuántas veces, **quién** lo vio, **qué hacía justo antes**, el contexto y la **traza completa**. Cada uno se marca *Visto* o *Resuelto*; si reaparece, se reabre solo. El botón *Copiar informe para TI* deja todo listo para pegar en un ticket.
3. **Administración → Actividad.** Historial de cada analista (pedidos guardados, análisis en SAP, cubicajes, importaciones, cambios de cuenta) con filtros por persona, tipo, resultado, fechas y búsqueda por código. Se descarga como CSV (con tildes bien en Excel).
4. **Mi actividad.** Cada analista ve solo su propio historial.
5. **Errores del navegador.** Una pantalla en blanco o un fallo de script también llegan al registro, con la página y el navegador.
6. **Archivo de log.** `od.log` tiene una línea JSON por petición (con el mismo código) y por error. Se busca con `findstr 3f9a1c0b7d od.log`.
7. **Errores de SAP.** Los fallos de una acción de SAP quedan con origen *SAP*, el usuario que la pidió y los argumentos.

### Monitoreo

- `GET /api/ping` → `{"ok": true}` sin pedir sesión y sin datos internos. Úselo en el balanceador o en el monitor de disponibilidad.
- *Administración → Servidor* muestra el tiempo activo, el tamaño de la base y del log, el espacio libre y una lista de revisión (cuentas, HTTPS, disco, base).

## 9. Actualizar la plataforma

1. Detener el servicio (`nssm stop OrderDesk`).
2. Copiar los archivos nuevos encima (no tocar `.env` ni `data\`).
3. `.venv\Scripts\pip install -r requirements.txt` y `.venv\Scripts\alembic upgrade head`.
4. Iniciar el servicio. Los navegadores toman los archivos nuevos solos.

## 10. Lista de verificación antes de abrirla al equipo

- [ ] Se entra por `https://orderdesk.empresa.cl` y el candado es válido.
- [ ] `COOKIE_SEGURA=1` y `AUTENTICACION=obligatoria`.
- [ ] El primer administrador cambió su clave y la línea `ADMIN_INICIAL` se borró.
- [ ] Cada analista tiene su cuenta (no hay cuentas compartidas).
- [ ] `/api/ping` responde y el monitor la vigila.
- [ ] Hay copia diaria de la base y de `data\archivos` fuera del servidor.
- [ ] El servicio se reinicia solo (probar apagando el proceso).
- [ ] El administrador sabe dónde ver *Errores* y *Actividad*.
