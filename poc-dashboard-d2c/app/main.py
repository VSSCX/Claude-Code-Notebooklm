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
from . import asistente, auditoria, auth, servicio, ventas
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


@app.middleware("http")
async def control_de_acceso(request: Request, call_next):
    """Todo /api/* exige sesion (cuando el acceso esta activo), el rol de la ruta, origen valido y un limite de uso. Lo demas es estatico, sin datos."""
    ruta = request.url.path
    request.state.usuario, request.state.rol = None, "admin"
    if ruta.startswith("/api/") and ruta not in auth.PUBLICAS and auth.requerida():
        falla = auth.problema_de_configuracion()
        if falla:
            return JSONResponse(status_code=503, content={"error": falla})
        ses = auth.leer_sesion(request.cookies.get(auth.COOKIE))
        if not ses:
            return JSONResponse(status_code=401, content={"error": "Inicia sesión para continuar."})
        request.state.usuario, request.state.rol = ses["usuario"], ses["rol"]
        if not auth.origen_valido(request.method, request.headers.get("origin"), request.headers.get("host")):
            auditoria.registrar("origen_rechazado", ses["usuario"], ruta=ruta)
            return JSONResponse(status_code=403, content={"error": "Origen no permitido."})
        if not auth.permitido(ses["rol"], ruta):
            auditoria.registrar("acceso_denegado", ses["usuario"], ruta=ruta, rol=ses["rol"])
            return JSONResponse(status_code=403, content={"error": "Tu rol no permite esta acción."})
        if auth.excede_limite(ses["usuario"], ruta):
            return JSONResponse(status_code=429, content={"error": "Demasiadas solicitudes. Espera un minuto."})
    return await call_next(request)


def _quien(request: Request) -> str:
    return getattr(request.state, "usuario", None) or "local"


@app.post("/api/login")
async def api_login(request: Request):
    """Usuario y clave -> cookie de sesion. Con bloqueo temporal tras 5 intentos fallidos (por usuario y por IP)."""
    c = await _cuerpo(request)
    usuario = str(c.get("usuario", ""))[:120].strip().lower()
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    falla = auth.problema_de_configuracion()
    if falla:
        return JSONResponse(status_code=503, content={"error": falla})
    if not auth.requerida():
        return {"ok": True, "auth": False, "rol": "admin"}
    if not auth.origen_valido("POST", request.headers.get("origin"), request.headers.get("host")):
        return JSONResponse(status_code=403, content={"error": "Origen no permitido."})
    claves = (f"u:{usuario}", f"ip:{ip}")
    if any(auth.bloqueado(k) for k in claves):
        auditoria.registrar("login_bloqueado", usuario, ip=ip)
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera 15 minutos."})
    ses = auth.iniciar_sesion(usuario, str(c.get("clave", ""))[:200])
    if not ses:
        for k in claves:
            auth.anotar_fallo(k)
        auditoria.registrar("login_fallido", usuario, ip=ip)
        return JSONResponse(status_code=401, content={"error": "Usuario o clave incorrectos."})
    for k in claves:
        auth.limpiar_fallos(k)
    auditoria.registrar("login_ok", ses["usuario"], ip=ip, rol=ses["rol"])
    resp = JSONResponse({"ok": True, "auth": True, "usuario": ses["usuario"], "rol": ses["rol"]})
    resp.set_cookie(auth.COOKIE, auth.crear_sesion(ses["usuario"], ses["rol"]), max_age=settings.sesion_horas * 3600, httponly=True,
                    samesite="strict", secure=settings.serverless or request.url.scheme == "https", path="/")
    return resp


@app.post("/api/logout")
def api_logout(request: Request):
    auditoria.registrar("logout", _quien(request))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/yo")
def api_yo(request: Request):
    """Quien soy y que puedo hacer (la pantalla oculta lo que el rol no permite; el servidor lo hace cumplir igual)."""
    if not auth.requerida():
        return {"auth": False, "usuario": None, "rol": "admin"}
    ses = auth.leer_sesion(request.cookies.get(auth.COOKIE))
    if not ses:
        return JSONResponse(status_code=401, content={"error": "Inicia sesión para continuar."})
    return {"auth": True, **ses}


@app.get("/api/salud")
def api_salud():
    """Publica y sin datos: para saber si el servicio esta arriba."""
    return {"ok": True}


@app.get("/api/auditoria")
def api_auditoria(n: int = 100):
    """Ultimos registros de la bitacora y si la cadena de hashes sigue integra (solo admin)."""
    return {"verificacion": auditoria.verificar(), "registros": auditoria.leer(max(1, min(n, 500)))}


@app.get("/api/calidad")
def api_calidad():
    """Resultado de los controles de calidad de la ultima carga (exactitud, completitud, consistencia, actualizacion, unicidad...)."""
    try:
        return servicio.informe_calidad()
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/linaje")
def api_linaje():
    """Linaje y procedencia de los datos: fuentes, version, huellas, columnas incluidas y excluidas, responsable."""
    try:
        return servicio.linaje()
    except Exception as e:  # noqa: BLE001
        return _error(e)


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
    auditoria.registrar("exporta_ventas", _quien(request), clasif2=cl, filtros=sorted(k for k, v in c.items() if v))
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
        auditoria.registrar("exporta_pedidos", _quien(request), filas=n, criticos=crit, filtros=sorted(k for k, v in c.items() if v))
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
def api_chat_historial(request: Request):
    """Para quien mantiene el programa: uso del asistente y las preguntas que no entendio (sin datos de pedidos)."""
    auditoria.registrar("consulta_historial_asistente", _quien(request))
    if settings.serverless:
        return JSONResponse(status_code=404, content={"error": "No disponible"})
    return asistente.memoria.estadisticas()


@app.get("/api/chat/aprendizaje")
def api_chat_aprendizaje():
    """Para quien mantiene el programa: que preguntas no se entendieron o no sirvieron, con la validada mas parecida."""
    if settings.serverless:
        return JSONResponse(status_code=404, content={"error": "No disponible"})
    return asistente.memoria.informe()


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
        res = await run_in_threadpool(asistente.responder, cuerpo.get("pregunta", ""), previo)
        auditoria.registrar("pregunta_asistente", _quien(request), pregunta=str(cuerpo.get("pregunta", ""))[:200], via=res.get("via"), ok=res.get("ok"))
        return res
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
def api_diagnostico(request: Request):
    """Cuanto tardo cada consulta en la ultima carga (para optimizar con datos reales)."""
    auditoria.registrar("consulta_diagnostico", _quien(request))
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


@app.get("/login.html", include_in_schema=False)
def login_html():
    return FileResponse(PUBLIC / "login.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# Todo se sirve desde aqui mismo (fuentes, librerias, estilos): las redes corporativas bloquean los CDN.
for _carpeta in ("css", "js", "fonts", "vendor", "img"):
    if (PUBLIC / _carpeta).is_dir():
        app.mount(f"/{_carpeta}", StaticFiles(directory=PUBLIC / _carpeta), name=_carpeta)
