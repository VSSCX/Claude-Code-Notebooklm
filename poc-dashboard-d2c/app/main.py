"""FastAPI del dashboard D2C. Sirve el frontend y expone los datos por /api."""
import mimetypes
import re
from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from . import asistente, servicio, ventas
from .seguridad import CABECERAS

log = logging.getLogger("dashboard")

PUBLIC = BASE_DIR / "public"   # los archivos estaticos viven en public/: asi Vercel los sirve directo desde su CDN

# Windows a veces no conoce estos tipos y el navegador rechazaria el archivo.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@asynccontextmanager
async def ciclo_de_vida(app):
    if not settings.serverless:     # una funcion sin servidor no puede mantener un hilo vivo entre llamadas
        servicio.iniciar_monitor()  # revisa cambios en segundo plano (consulta liviana)
    yield
    servicio.detener_monitor()


# En produccion (Vercel) no se publican /docs ni /openapi.json.
app = FastAPI(title="Dashboard D2C · Order Desk", version="3.1.0", lifespan=ciclo_de_vida,
              docs_url=None if settings.serverless else "/docs",
              redoc_url=None, openapi_url=None if settings.serverless else "/openapi.json")


app.add_middleware(GZipMiddleware, minimum_size=1024)   # el JSON del tablero baja de ~125 KB a ~10 KB; tambien comprime js y css


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    resp = await call_next(request)
    for k, v in CABECERAS.items():
        resp.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"      # los datos nunca se guardan en cache intermedia
    return resp


def _error(e: Exception) -> JSONResponse:
    """Localmente el analista necesita el detalle (VPN, driver, credenciales); publicado, solo un mensaje generico."""
    log.exception("Fallo al atender la consulta")
    msg = "No se pudo obtener los datos en este momento." if settings.serverless else str(e)
    return JSONResponse(status_code=503, content={"error": msg})

@app.post("/api/dashboard")
async def api_dashboard(request: Request):
    try:
        filtros = await request.json()
    except Exception:
        filtros = {}
    if not isinstance(filtros, dict):
        filtros = {}
    try:
        return servicio.obtener(filtros)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/filtros")
def api_filtros():
    try:
        return servicio.opciones_filtros()
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/pedido/{sequence}")
def api_pedido(sequence: str):
    """Cabecera y lineas (codigo SAP, descripcion, cantidad, precio, monto) de un pedido, para el cajon de detalle."""
    if not sequence.isdigit() or len(sequence) > 14:
        return JSONResponse(status_code=400, content={"error": "Sequence invalido"})
    try:
        det = servicio.detalle_pedido(sequence)
    except Exception as e:  # noqa: BLE001
        return _error(e)
    return det if det else JSONResponse(status_code=404, content={"error": "Pedido no encontrado"})


async def _cuerpo(request: Request) -> dict:
    try:
        c = await request.json()
    except Exception:
        return {}
    return c if isinstance(c, dict) else {}


@app.post("/api/ventas")
async def api_ventas(request: Request):
    """Ventas por Clasif2 de la maestra de productos (y por producto de una clasificacion), con los filtros del tablero."""
    c = await _cuerpo(request)
    try:
        return await run_in_threadpool(ventas.ventas, c, c.get("zoom_clasif") if isinstance(c.get("zoom_clasif"), str) else None)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.post("/api/ventas/exportar")
async def api_ventas_exportar(request: Request):
    """CSV Clasif2 | Producto | Venta de una clasificacion (clasif2) o de todas (sin clasif2), respetando los filtros."""
    c = await _cuerpo(request)
    cl = c.get("zoom_clasif") if isinstance(c.get("zoom_clasif"), str) else None
    try:
        csv = await run_in_threadpool(ventas.exportar_csv, c, cl)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:  # noqa: BLE001
        return _error(e)
    nombre = "ventas-" + (re.sub(r"[^A-Za-z0-9]+", "-", cl).strip("-").lower() if cl else "todas") + ".csv"
    return Response(content=csv.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@app.post("/api/pedidos/exportar")
async def api_pedidos_exportar(request: Request):
    """CSV con TODOS los pedidos que dejan los filtros del tablero (criticos=true: los facturados en SAP y pendientes en VTEX)."""
    c = await _cuerpo(request)
    crit = c.pop("criticos", False) is True
    try:
        csv, n = await run_in_threadpool(servicio.exportar_pedidos, c, crit)
    except Exception as e:  # noqa: BLE001
        return _error(e)
    nombre = "pedidos-facturados-pendientes.csv" if crit else "pedidos.csv"
    return Response(content=csv.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"', "X-Filas": str(n)})


@app.get("/api/chat/motor")
def api_chat_motor():
    m = asistente.memoria
    return {**asistente.info_motor(), "ejemplos": asistente.EJEMPLOS, "frecuentes": m.frecuentes(6), "recientes": m.recientes(6)}


@app.post("/api/chat/valorar")
async def api_chat_valorar(request: Request):
    """Pulgar arriba o abajo de una respuesta: alimenta la memoria del asistente (ver app/asistente/memoria.py)."""
    c = await _cuerpo(request)
    ok = asistente.memoria.valorar(str(c.get("id", "")), c.get("util") if isinstance(c.get("util"), bool) else None)
    return {"ok": ok}


@app.get("/api/chat/historial")
def api_chat_historial():
    """Para quien mantiene el programa: uso del asistente y las preguntas que no entendio (sin datos de pedidos)."""
    if settings.serverless:
        return JSONResponse(status_code=404, content={"error": "No disponible"})
    return asistente.memoria.estadisticas()


@app.post("/api/chat")
async def api_chat(request: Request):
    """Pregunta en lenguaje natural -> plan validado -> cifra calculada por el servidor (ver asistente.py)."""
    try:
        cuerpo = await request.json()
    except Exception:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    previo = cuerpo.get("previo") if isinstance(cuerpo.get("previo"), dict) else None
    try:
        return await run_in_threadpool(asistente.responder, cuerpo.get("pregunta", ""), previo)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/version")
def api_version():
    """Barata: no toca SQL. El navegador la consulta seguido para saber si hay datos nuevos."""
    return servicio.estado_version()


@app.get("/api/config")
def api_config():
    return {"poll": settings.navegador_cada, "demo": settings.demo,
            "simulable": settings.demo and not settings.serverless,   # el pedido simulado vive en memoria: en Vercel cada instancia tendria el suyo
            "fecha_validada": settings.fecha_validada}


@app.get("/api/diagnostico")
def api_diagnostico():
    """Cuanto tardo cada consulta en la ultima carga (para optimizar con datos reales)."""
    if settings.serverless:
        return JSONResponse(status_code=404, content={"error": "No disponible"})
    return servicio.diagnostico()


@app.post("/api/demo/pedido")
def api_demo_pedido():
    """Solo en modo demo: simula la llegada de un pedido nuevo para ver la actualizacion en vivo."""
    if not settings.demo or settings.serverless:
        return JSONResponse(status_code=404, content={"error": "Solo disponible en modo DEMO local"})
    from .demo import agregar_pedido
    return agregar_pedido()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(PUBLIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# Todo se sirve desde aqui mismo (fuentes, librerias, estilos): las redes corporativas bloquean los CDN.
for _carpeta in ("css", "js", "fonts", "vendor", "img"):
    if (PUBLIC / _carpeta).is_dir():
        app.mount(f"/{_carpeta}", StaticFiles(directory=PUBLIC / _carpeta), name=_carpeta)
