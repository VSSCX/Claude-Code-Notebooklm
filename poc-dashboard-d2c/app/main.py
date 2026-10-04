"""FastAPI del dashboard D2C. Sirve el frontend y expone los datos por /api."""
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from . import servicio

WEB = BASE_DIR / "web"

# Windows a veces no conoce estos tipos y el navegador rechazaria el archivo.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@asynccontextmanager
async def ciclo_de_vida(app):
    servicio.iniciar_monitor()      # revisa cambios en segundo plano (consulta liviana)
    yield
    servicio.detener_monitor()


app = FastAPI(title="Dashboard D2C · Order Desk", version="3.0.0", lifespan=ciclo_de_vida)


@app.post("/api/dashboard")
async def api_dashboard(request: Request):
    try:
        filtros = await request.json()
    except Exception:
        filtros = {}
    try:
        return servicio.obtener(filtros or {})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"error": str(e)})


@app.get("/api/filtros")
def api_filtros():
    try:
        return servicio.opciones_filtros()
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"error": str(e)})


@app.get("/api/version")
def api_version():
    """Barata: no toca SQL. El navegador la consulta seguido para saber si hay datos nuevos."""
    return servicio.estado_version()


@app.get("/api/config")
def api_config():
    return {"poll": settings.navegador_cada, "demo": settings.demo,
            "fecha_validada": settings.fecha_validada}


@app.get("/api/diagnostico")
def api_diagnostico():
    """Cuanto tardo cada consulta en la ultima carga (para optimizar con datos reales)."""
    return servicio.diagnostico()


@app.post("/api/demo/pedido")
def api_demo_pedido():
    """Solo en modo demo: simula la llegada de un pedido nuevo para ver la actualizacion en vivo."""
    if not settings.demo:
        return JSONResponse(status_code=404, content={"error": "Solo disponible en modo DEMO"})
    from .demo import agregar_pedido
    return agregar_pedido()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# Todo se sirve desde aqui mismo (fuentes, librerias, estilos): las redes corporativas bloquean los CDN.
for _carpeta in ("css", "js", "fonts", "vendor", "img"):
    app.mount(f"/{_carpeta}", StaticFiles(directory=WEB / _carpeta), name=_carpeta)
