# Dashboard D2C en Vercel — estado y auditoría

**Estado: listo para desplegar en modo DEMO (datos de ejemplo). No está desplegado ni se probó en Vercel**
(no hay sesión de Vercel en este entorno); todo lo de abajo se verificó localmente simulando cómo corre allá
(`VERCEL=1`). El modo real (SQL Server de VTEX y SAP) **no puede correr en Vercel** tal como está; ver la sección
"Por qué el modo real no corre en Vercel".

## Cómo desplegarlo

1. Vercel → *Add New… → Project* → importar `VSSCX/Claude-Code-Notebooklm` (rama del PR o `main` una vez mergeado).
2. **Root Directory:** `poc-dashboard-d2c` · **Framework Preset:** `Other` · sin *Build Command* ni *Output Directory*.
3. No hace falta ninguna variable de entorno (Vercel define `VERCEL=1` y eso fuerza el modo demo).
4. *Deploy*. Desde consola, en la carpeta `poc-dashboard-d2c`: `vercel` (vista previa) y `vercel --prod` solo cuando quieras producción.
5. Si algún día pasa a datos reales: activar *Settings → Deployment Protection* (Vercel Authentication o contraseña) **antes**.
   La app no tiene inicio de sesión propio.

Cómo está armado: `public/` (HTML, CSS, JS, fuentes, Chart.js) lo sirve la CDN de Vercel; `api/index.py` es la función
Python que atiende `/api/*` (`vercel.json` hace la redirección); `requirements.txt` instala `pyodbc` solo en Windows.

## Por qué el modo real no corre en Vercel

| Obstáculo | Detalle |
|---|---|
| Red | El ODS de SAP (`clws0156`) es un servidor interno: no se llega desde Internet ni desde Vercel (hoy se necesita VPN o estar en la red). |
| Driver | Vercel no trae el driver ODBC de SQL Server y `pyodbc` no se compila allí. |
| Estado en memoria | El cálculo se guarda en memoria y un hilo revisa cambios cada 10 s. Una función sin servidor no mantiene hilos ni memoria entre llamadas. |
| Credenciales | Pondría usuario y clave de las bases en un servicio público de terceros. |

Para tener datos reales en Vercel hace falta una decisión de arquitectura (no se hizo): por ejemplo, un proceso dentro de la red
que publique los datos ya calculados a una base accesible desde Internet (Postgres administrado) y que la función solo lea de ahí,
con login corporativo delante. Mientras tanto, el dashboard real sigue corriendo en el PC de cada analista con `POC_Dashboard.py`.

## Qué hace distinto en Vercel (y por qué)

- Solo demo: `VERCEL=1` fuerza `DEMO`; nunca intenta conectarse a las bases.
- Sin hilo de monitoreo; el navegador pregunta cada 30 s (no cada 2 s) para no gastar invocaciones.
- La campana de notificaciones no recibe avisos (en demo sobre Vercel no entran pedidos nuevos); cuando haya datos reales, cada notificación se guarda solo en el navegador de cada persona (no se comparte entre analistas).
- Sin botón «Simular pedido» (el pedido simulado viviría en la memoria de una sola instancia).
- No se publican `/docs`, `/openapi.json`, `/api/diagnostico` ni `/api/demo/pedido`.
- El detalle de un pedido y el asistente de consultas funcionan con los datos de ejemplo (el asistente solo con reglas). No configures `IA_MODO` ni claves en un despliegue público: no tiene usuario ni clave, y el tope de 40 preguntas por minuto es por instancia, no global.
- Los errores devuelven un mensaje genérico (en el PC del analista siguen mostrando el detalle: VPN, driver, credenciales).

## Auditoría

Se corre con `python verificar_vercel.py` (44 comprobaciones; sale con código 1 si algo falla). Resultado actual: **todo en orden**.

| Área | Qué se comprobó | Resultado |
|---|---|---|
| Configuración | `vercel.json` válido, redirección `/api/*`, `api/index.py` expone `app`, versión de Python fijada | OK |
| Dependencias | `pyodbc` condicionado a Windows; versiones con tope de versión mayor; sin paquetes de desarrollo | OK |
| Estáticos | Todo local (cero URLs externas: sin Google Fonts ni CDN), `public/` pesa ~390 KB, sin scripts en línea | OK |
| Servidor (`VERCEL=1`) | Demo forzado, sin hilo, `/api/*` con `no-store`, rutas de diagnóstico ocultas, cuerpo inválido no rompe | OK |
| Seguridad | CSP estricta (`script-src 'self'`, sin `unsafe-eval`), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, HSTS; mismas cabeceras en `vercel.json` (estáticos) y en el servidor (API) | OK |
| Accesibilidad | axe-core (WCAG 2.0/2.1 A y AA + buenas prácticas) en 15 combinaciones: 3 pantallas × claro/oscuro × 1440, 390 y TV 1920 | **0 violaciones**; sin errores de CSP en consola |
| Guías web de Vercel (*Web Interface Guidelines*) | Revisión de `index.html`, `app.css` y los módulos de `public/js` | Aplicadas: enlace «Saltar al contenido», `h1`, landmarks, `name`/`autocomplete`/`spellcheck` en controles, `translate="no"`, espacios duros en montos, comillas tipográficas, `text-wrap: balance`, `touch-action`, `theme-color`, `viewport-fit` y áreas seguras, precarga de fuentes, dimensiones del logo, lecturas de layout agrupadas, vista en la URL (`#resumen`) |
| Diseño (Impeccable) | Detector mecánico + revisión final con subagente | 3 avisos, todos justificados: la barra de carga de 3 px (no es un borde de tarjeta) y un falso positivo de relleno |
| Comportamiento | Playwright: foco y texto del buscador, scroll y gráficos se conservan al llegar un pedido; tema, modo TV, orden por teclado, persistencia | OK |

### Revisión del rediseño (referencia Ant / Enterprise)

La interfaz se rehízo con la skill de diseño **Ant** (awesome-design-skills), reglas de **taste-skill** y la extracción de **image-to-code**
(sin imagen generada: se usó la vista previa de la referencia y su DESIGN.md). Se revisó con **playwright-cli** (árbol de accesibilidad,
consola, clic en la campana, capturas de escritorio y móvil), Playwright, axe-core y `verificar_vercel.py`. Resultado tras el rediseño:
axe-core **0 violaciones** en las 15 combinaciones, sin errores de consola ni de CSP, 32 comprobaciones de `verificar_vercel.py` en orden
(incluye «sin rayas largas»). Íconos: Tabler (MIT) locales; fuentes: Plus Jakarta Sans y JetBrains Mono locales.

### Pendiente o a tu criterio

- **Sin inicio de sesión:** cualquiera con la URL ve la app. En demo no hay datos reales; con datos reales, Deployment Protection es obligatorio.
- **Sin límite de peticiones:** si se expone públicamente, activar el Firewall de Vercel (rate limiting).
- **Filtros no viajan en la URL** (solo la pantalla: `#pedidos`, `#resumen`, `#diagnostico`). Las guías lo recomiendan; no se hizo para no tocar el contrato del servidor.
- **Tabla de hasta 500 filas sin virtualizar** (el servidor ya limita a 500). Si se sube ese tope, conviene virtualizar.
- **Fechas `dd-mm-aa` fijas** por fidelidad al reporte de Power BI (los números sí usan `Intl`).
- **No verificado en Vercel:** el build real, el tiempo de arranque en frío (pandas ≈ 120 MB instalados; el límite de la función es 500 MB), `maxDuration` según tu plan, y que la redirección `/api/*` se comporte igual que en local.
- **Pandas 2.x no se probó aquí** (se probó con pandas 3.0, numpy 2.4, FastAPI 0.142); `requirements.txt` permite ambas.
- **Gráfico de cierre con 2+ meses** (segunda serie en gris `--muted`): no se pudo ver con los datos de ejemplo (solo hay un mes cerrado).
