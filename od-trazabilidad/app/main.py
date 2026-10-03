import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import BASE_DIR, settings
from .db import get_session
from .integrations import acciones
from .models import Archivo
from .routers.api import router

WEB = BASE_DIR / "web"

log = logging.getLogger("plataforma")



@asynccontextmanager
async def _vida(_app):
    """Lo que se hace al abrir la plataforma."""
    _cargar_conexion_bases()
    _respaldo_al_iniciar()
    _rellenar_flujo()
    yield


app = FastAPI(title="Trazabilidad Order Desk", version="0.1.0", lifespan=_vida)
app.include_router(router)
@app.middleware("http")
async def _sesion_y_usuario(request, call_next):
    """Quién hace la acción (para el historial) y, si hay clave, que haya entrado."""
    from . import domain
    from .usuarios import limpio, sesion_valida, requiere_clave
    domain.usar_usuario(limpio(request.headers.get("x-usuario", "")))
    ruta = request.url.path
    protegida = (ruta.startswith(("/archivos/", "/visor/"))
                 or (ruta.startswith("/api/") and not ruta.startswith("/api/sesion")))
    if protegida and requiere_clave() and not sesion_valida(request.cookies.get("sesion", "")):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Sesión no iniciada."}, status_code=401)
    return await call_next(request)


def _cargar_conexion_bases():
    """Toma los datos de SQL Server guardados en Configuración, si los hay."""
    import json as _json
    from .db import SessionLocal
    from .integrations import bases
    from .models import Config
    try:
        with SessionLocal() as s:
            c = s.get(Config, bases.CLAVE_CONFIG)
            if c is not None:
                bases.usar_conexion(_json.loads(c.valor))
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo leer la conexión guardada: %s", e)


def _rellenar_flujo():
    """Los análisis y cubicajes hechos antes de que existiera el resumen del flujo lo reciben ahora."""
    from . import domain
    from .db import SessionLocal
    try:
        with SessionLocal() as s:
            n = domain.rellenar_flujo(s)
            s.commit()
        if n:
            log.info("Resumen de flujo creado para %s pedidos", n)
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo preparar el resumen del flujo: %s", e)


def _respaldo_al_iniciar():
    """Copia de seguridad diaria: se hace sola al abrir la plataforma."""
    from .respaldo import copiar
    r = copiar("inicio")
    if r.get("ok"):
        log.info("Respaldo del día: %s (%s copias guardadas)", r["archivo"], r["copias"])
    else:
        log.info("Sin respaldo: %s", r.get("motivo"))


app.mount("/js", StaticFiles(directory=WEB / "js"), name="js")
app.mount("/css", StaticFiles(directory=WEB / "css"), name="css")
app.mount("/fonts", StaticFiles(directory=WEB / "fonts"), name="fonts")
app.mount("/vendor", StaticFiles(directory=WEB / "vendor"), name="vendor")
VISORES = Path(settings.visores_dir)
VISORES.mkdir(parents=True, exist_ok=True)
app.mount("/visor", StaticFiles(directory=VISORES), name="visor")


@app.get("/archivos/{aid}", include_in_schema=False)
def archivo(aid: int, s: Session = Depends(get_session)):
    a = s.get(Archivo, aid)
    ruta = acciones.DIR_ARCHIVOS / a.archivo if a else None
    if a is None or not ruta.exists():
        raise HTTPException(404, "Archivo no encontrado.")
    # inline: el visor y los PDF se muestran dentro de la plataforma en vez de descargarse
    tipo, _ = mimetypes.guess_type(a.archivo)
    return FileResponse(ruta, filename=a.nombre, media_type=tipo or "application/octet-stream",
                        content_disposition_type="inline")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})
