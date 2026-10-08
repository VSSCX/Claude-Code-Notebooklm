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
    _iniciar_cuentas_y_registro()
    _cargar_conexion_bases()
    _respaldo_al_iniciar()
    _rellenar_flujo()
    yield


app = FastAPI(title="Trazabilidad Order Desk", version="0.1.0", lifespan=_vida)
app.include_router(router)
PUBLICAS_API = ("/api/sesion", "/api/log/cliente", "/api/ping")
ESCRITURA = ("POST", "PUT", "PATCH", "DELETE")


def _json(codigo: int, detalle: str, rid: str, **extra):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": detalle, "codigo": rid, **extra}, status_code=codigo, headers={"X-Request-ID": rid})


@app.middleware("http")
async def _sesion_y_registro(request, call_next):
    """Quién hace la acción, que haya entrado (si hay cuentas), y el registro de actividad y errores."""
    import time

    from . import domain, registro, seguridad
    from .db import SessionLocal
    from .usuarios import limpio, requiere_clave, sesion_valida
    inicio = time.perf_counter()
    rid = registro.nuevo_request_id()
    ruta, metodo = request.url.path, request.method
    ip = request.client.host if request.client else ""
    es_api = ruta.startswith("/api/")
    protegida = ruta.startswith(("/archivos/", "/visor/")) or (es_api and not ruta.startswith(PUBLICAS_API))
    cuenta, exige = None, False
    try:
        with SessionLocal() as s:
            exige = seguridad.exige_entrar(s)
            if exige:
                u = seguridad.usuario_de(s, request.cookies.get(seguridad.COOKIE, ""))
                if u is not None:
                    cuenta = {"id": u.id, "usuario": u.usuario, "nombre": u.nombre or u.usuario, "rol": u.rol,
                              "debe_cambiar_clave": bool(u.debe_cambiar_clave)}
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo revisar la sesión: %s", e)
    request.state.cuenta = cuenta
    quien = cuenta["usuario"] if cuenta else limpio(request.headers.get("x-usuario", ""))
    domain.usar_usuario(cuenta["nombre"] if cuenta else quien)
    registro.fijar_quien(quien, ip, ruta, metodo)

    resp = None
    if protegida and exige and cuenta is None:
        resp = _json(401, "Sesión no iniciada.", rid)
    elif protegida and not exige and requiere_clave() and not sesion_valida(request.cookies.get("sesion", "")):
        resp = _json(401, "Sesión no iniciada.", rid)
    elif es_api and metodo in ESCRITURA and request.headers.get("x-requested-with") != "od" and exige:
        resp = _json(403, "Petición no permitida (falta la cabecera de seguridad).", rid)
    elif (cuenta and cuenta["debe_cambiar_clave"] and es_api and not ruta.startswith(PUBLICAS_API)
          and not ruta.startswith(("/api/mi",))):
        resp = _json(403, "Debes cambiar tu clave antes de continuar.", rid, cambiar_clave=True)
    if resp is None:
        try:
            resp = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            registro.registrar_excepcion(exc, rid=rid, status=500)
            resp = _json(500, f"Error interno. Código de seguimiento: {rid}", rid)
    ms = int((time.perf_counter() - inicio) * 1000)
    resp.headers["X-Request-ID"] = rid
    if ruta.startswith(("/js/", "/css/", "/vendor/", "/visor/")):
        # El navegador revalida cada vez (barato: 304): tras actualizar el instalador nunca queda una mezcla de archivos nuevos y viejos
        resp.headers["Cache-Control"] = "no-cache"
    if es_api:
        st = resp.status_code
        if st >= 400 or not ruta.startswith(("/api/version", "/api/ping")):      # el sondeo cada 10 s no llena el log
            registro.linea(tipo="acceso", rid=rid, usuario=quien, metodo=metodo, ruta=ruta, status=st, ms=ms, ip=ip)
        desc = registro.describir(metodo, ruta)
        if desc and (metodo != "GET" or st < 400):
            cat, texto, ent = desc
            if st < 400:
                res = "ok"
            elif st < 500:
                res = "rechazada"
            else:
                res = "error"
            registro.registrar_actividad(quien, cat, texto, entidad=ent, resultado=res, ms=ms, ip=ip, rid=rid,
                                         detalle="" if res == "ok" else f"HTTP {st}")
    return resp


@app.exception_handler(HTTPException)
async def _http_error(request, exc):
    """Los errores del servidor (5xx) también quedan en el registro; los de uso (400-499) no son fallas."""
    from fastapi.responses import JSONResponse

    from . import registro
    rid = registro.request_id()
    if exc.status_code >= 500:
        registro.registrar_error("servidor", f"HTTP {exc.status_code}: {exc.detail}", status=exc.status_code, rid=rid)
        detalle = f"{exc.detail} (código {rid})"
    else:
        detalle = exc.detail
    return JSONResponse({"detail": detalle, "codigo": rid}, status_code=exc.status_code,
                        headers={**(exc.headers or {}), "X-Request-ID": rid})


def _iniciar_cuentas_y_registro():
    """Logs en archivo, primera cuenta administradora (ADMIN_INICIAL) y limpieza de lo antiguo."""
    from . import registro, seguridad
    from .db import SessionLocal
    try:
        registro.configurar_logs()
        from .integrations import sap
        sap.carpeta_export()                    # la carpeta de la exportación de SAP se crea (y comprueba) al arrancar
        with SessionLocal() as s:
            u = seguridad.crear_admin_inicial(s)
            if u:
                log.info("Cuenta administradora creada: %s", u)
            nuevos = seguridad.crear_usuarios_iniciales(s)
            if nuevos:
                log.info("Cuentas creadas desde el .env: %s", ", ".join(nuevos))
        registro.purgar()
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo preparar el registro o la carpeta de exportación: %s", e)


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
    """La página lleva una versión en cada script y estilo: tras actualizar, el navegador pide los nuevos
    aunque tenga guardados los viejos (antes quedaba una mezcla y la pantalla salía en blanco)."""
    import hashlib
    import re

    from fastapi.responses import HTMLResponse
    huella = hashlib.sha1()
    for carpeta in ("js", "css", "vendor"):
        for f in sorted((WEB / carpeta).glob("*")):
            if f.is_file():
                st = f.stat()
                huella.update(f"{f.name}{st.st_size}{int(st.st_mtime)}".encode())
    ver = huella.hexdigest()[:10]
    html = (WEB / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'((?:src|href)="/(?:js|css|vendor)/[^"?]+)"', lambda m: f'{m.group(1)}?v={ver}"', html)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
