"""FastAPI del dashboard D2C. Sirve el frontend y expone los datos por /api."""
import mimetypes
from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from . import servicio
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
