# Trazabilidad Order Desk

Plataforma para seguir cada pedido desde que llega la OC hasta el pack list. El seguimiento es por producto y por entrega, y la plataforma recibe los datos directamente de las macros de SAP.

## Arquitectura

```
 Navegador (web/index.html)          Excel + SAP GUI
        │  REST /api                     │  TrazWeb.bas  ── POST /api/paquetes
        ▼                                ▼
 ┌──────────────────────── FastAPI (app/) ────────────────────────┐
 │ routers/api.py   domain.py (reglas)   integrations/excel.py    │
 │                      │                    └─ ejecuta macros COM│
 │                SQLAlchemy + Alembic                            │
 └──────────────────────┬─────────────────────────────────────────┘
                        ▼
      SQLite (fase 1)  →  SQL Server (fase 2, Power BI directo)
```

### Por qué este stack

- **Python + FastAPI**: API tipada, documentación automática en `/docs` y pocas dependencias. Además corre en tu PC, así que puede ejecutar macros de Excel/SAP, cosa que ninguna web en la nube puede hacer.
- **SQLAlchemy + Alembic**: el mismo código funciona con SQLite hoy y con SQL Server mañana, cambiando solo `DATABASE_URL`. Los cambios de estructura quedan versionados en `migrations/`.
- **Frontend sin build** (HTML + JS): se sirve desde el mismo servidor, sin Node ni compilación. Solo accede a los datos a través del objeto `Store`, así que si el equipo crece se puede reemplazar por React sin tocar la API.
- **Todo local en la fase 1**: los datos de clientes no salen de tu equipo, lo que evita discusiones con TI mientras validas el modelo.

## Instalación (Windows)

1. Necesitas Python 3.11 o superior (`py --version`). Si no lo tienes, instálalo desde python.org (sin permisos de administrador: "Install for me only") o pídelo a TI.
2. Copia la carpeta a tu equipo, por ejemplo `C:\Users\<tu usuario>\od-trazabilidad`.
3. Doble clic en **run.bat**. La primera vez crea el entorno, instala las dependencias, crea la base y abre `http://127.0.0.1:8000`.
4. Edita `.env` con la ruta real de tu libro de automatización.

Si `pip` falla por el proxy corporativo: `pip install --proxy http://usuario:clave@proxy:puerto -r requirements.txt`, o pide a TI que habilite pypi.org.

## Conectar el libro de automatización

1. En el editor VBA: *Archivo → Importar archivo* → `vba/TrazWeb.bas`.
2. Agrega los enganches (una línea cada uno):

| Módulo | Dónde | Línea |
|---|---|---|
| Extraer_Datos_VL01N | después de `Trazabilidad_RegistrarPedido` | `TrazWeb_Exportar "pedido"` |
| Crear_Entregas | después de `Trazabilidad_BatchEntregas` | `TrazWeb_Exportar "entregas"` |
| Crear_Grupos | después de `Trazabilidad_BatchGrupos` | `TrazWeb_Exportar "grupos"` |
| Actualizar_FechayHora | inicio de la macro | `Dim gOk As Object: Set gOk = CreateObject("Scripting.Dictionary")` |
| | antes de `exitosos = exitosos + 1` | `If Not gOk.Exists(grupoNum) Then gOk.Add grupoNum, 1` |
| | después de `Next gk` | `TrazWeb_Exportar "fecha_sap", gOk` |

Al terminar, cada macro envía su paquete a `http://127.0.0.1:8000/api/paquetes`. Si la plataforma está cerrada, el paquete queda copiado en el portapapeles (se carga con Ctrl+V en la web). En ambos casos se guarda una copia en `Trazabilidad_Web\*.json`, al lado del libro.

**Ejecutar acciones desde la web**: importa también `vba/TrazWebAcciones.bas` y configura `MACROS_WORKBOOK` y `ACCIONES_HABILITADAS` en `.env`. El catálogo está en `app/integrations/acciones.py`: actualizar bases, cubicar, simular, visor 3D, leer pedido, crear entregas, crear grupos y limpiar. Corre una a la vez, solo las habilitadas, y `run.bat` debe estar abierto con tu usuario porque SAP GUI necesita tu sesión.

Cada acción devuelve una cadena de estado: si empieza con `ERROR`, la plataforma la muestra en rojo y no toca los datos. El visor 3D devuelve la ruta del HTML y la plataforma guarda una copia en el pedido.

**Borrado en SAP**: `eliminar_entrega` existe en el catálogo pero viene deshabilitado, y su macro (`TrazWeb_EliminarEntregaSAP`) devuelve ERROR a propósito. Para activarlo hay que grabar en SAP la secuencia real de VL02N, incluyendo las verificaciones previas (sin salida de mercancía, sin factura, sin grupo), y recién ahí agregar `eliminar_entrega` a `ACCIONES_HABILITADAS`.

## Modelo de datos

| Tabla | Contenido |
|---|---|
| `pedidos` | N° pedido SAP, OC, cliente, canal |
| `lineas_pedido` | SKU, cantidad del pedido, `externa` (unidades en entregas SAP anteriores a la plataforma) |
| `entregas` | N° entrega, grupo, N° cita, fecha/hora, vehículo, carga, UN, región, factura, anulada |
| `lineas_entrega` | SKU y cantidad por entrega |
| `pasos_entrega` | estado actual de cada paso |
| `eventos` | historial con fecha, hora y origen (web / script) |
| `archivos` | visores 3D generados y PDFs subidos, por pedido o camión |

Reglas:

- Pendiente = pedido − en entregas − externa.
- Un camión = entregas con el mismo N° de cita.
- Pasos: cita pedida → cita confirmada (exige fecha y hora) → fecha en SAP → ETQ → portal de despacho → proyección → facturada (exige N° de factura) → pack list → entregado.
- Reprogramar una cita reabre: confirmada, SAP, portal y proyección.
- El script nunca baja la cantidad de un pedido.
- La celda E2 del libro define unidad de negocio (MDA/SDA) y modalidad (Stock/Predistribuido).
- El paquete acepta OC y fecha del pedido, y solo las completa si están vacías (no pisa lo que edites a mano). Hoy el script todavía no las envía: pendiente leerlas desde la pantalla de VL01N.

## API

Documentación interactiva en `http://127.0.0.1:8000/docs`.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/estado` | todo lo que carga la web |
| GET | `/api/version` | detección de cambios (la web consulta cada 10 s) |
| PUT/DELETE | `/api/pedidos/{n}` | alta, edición y borrado (con sus entregas) |
| PUT/DELETE | `/api/entregas/{n}` | ídem |
| POST | `/api/paquetes` | paquetes del script VBA |
| GET/POST | `/api/acciones`, `/api/acciones/{id}` | listar y ejecutar acciones |
| POST/DELETE | `/api/archivos` | subir y quitar adjuntos |

## Desarrollo

- `test.bat` corre las pruebas (`tests/`), que incluyen el flujo completo con datos reales de tu libro.
- Si cambias `app/models.py`, genera una migración: `alembic revision --autogenerate -m "descripcion"` y luego `alembic upgrade head`.

## Herramientas

| Comando | Para qué |
|---|---|
| `py herramientas\\probar_sql.py [filtro] [--columnas]` | Probar la conexión a SQL Server y listar tablas/vistas |
| `py herramientas\\probar_sap.py PEDIDO PUESTO dd.MM.yyyy ["libro.xlsm"]` | Leer un pedido de VL01N con Python y compararlo con el Excel |
| `py herramientas\\capturar_caso.py "libro.xlsm" nombre` | Congelar un caso de control del cubicaje |

`app/integrations/sap.py` es el port de `Extraer_Datos_VL01N.bas`: mismos IDs de pantalla y
mismas tolerancias. Solo lee; no crea ni borra nada en SAP.

## Casos de control del cubicaje

Antes de portar el cubicaje a Python hay que congelar lo que hoy produce el Excel:

```
py herramientas/capturar_caso.py "V:\ruta\libro.xlsm" mda_paris_399
```

Guarda en `casos/` la entrada (parámetros, posiciones, medidas, pallet, camiones) y el
resultado esperado (hojas 03 y 04). `tests/test_casos.py` los valida, y cuando exista el
motor en Python un caso pasará solo si reproduce esas hojas exactamente.

Casos mínimos a capturar: MDA, SDA Stock, SDA Predistribuido, uno con caja master que no
cabe en el pallet y uno de HITES con segregación de calefones.

## Hoja de ruta

1. **Fase 1 (esta)**: uso personal en tu PC, SQLite, macros conectadas.
2. **Fase 2 (equipo)**:
   - servidor de la empresa con `DATABASE_URL` apuntando a SQL Server (y Power BI leyendo las tablas directo);
   - login corporativo (Microsoft Entra ID) antes de abrirlo a otros analistas;
   - las macros siguen corriendo en el PC de cada analista y envían a la URL del servidor.
3. **Fase 3 (integraciones)**:
   - lectura de SAP por OData o RFC (lo habilita TI/Basis) en vez del scripting de GUI;
   - ETQ, portal de despacho y portales de clientes: validar portal por portal si hay API o si se permite RPA.

## Límites conocidos

- `TrazWeb.bas` no se probó dentro de Excel, solo se simuló su salida con el libro real. Pruébalo con un pedido antes de usarlo a diario.
- `ActualizarFechaYReferencia` cuenta un grupo como exitoso aunque falle la escritura de la fecha, porque esa parte usa `On Error Resume Next`.
- Sin autenticación: el servidor escucha solo en `127.0.0.1`, así que no es accesible desde otros equipos.
