"""Registro de lo que pasa en la plataforma, para poder seguirle la pista a un problema.

- **Código de petición** (X-Request-ID): cada llamada lleva uno; sale en el historial, en los errores y en el log
  del servidor. Si un analista reporta "me salió un error", con ese código se llega a la línea exacta.
- **Actividad**: qué hizo cada analista y cuándo (guardar un pedido, analizar en SAP, crear entregas…).
- **Errores**: los repetidos se agrupan (primera vez, última, cuántas veces, quiénes) y llevan la traza completa.
- **Log en archivo**: una línea JSON por petición y por error, con rotación.

Todo es a prueba de fallas: registrar nunca debe romper la acción que se estaba haciendo.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
import traceback
import uuid
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import delete, select

from .config import settings
from .db import SessionLocal
from .models import Actividad, ErrorLog, ErrorOcurrencia, ahora

log = logging.getLogger("plataforma")
_acceso = logging.getLogger("od.acceso")
_rid: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_quien: contextvars.ContextVar[dict] = contextvars.ContextVar("quien", default={})
_SECRETOS = re.compile(r"clave|pass|token|secret|cookie|authorization", re.I)


def nuevo_request_id() -> str:
    rid = uuid.uuid4().hex[:10]
    _rid.set(rid)
    return rid


def request_id() -> str:
    return _rid.get()


def fijar_quien(usuario: str = "", ip: str = "", ruta: str = "", metodo: str = "") -> None:
    _quien.set({"usuario": usuario, "ip": ip, "ruta": ruta, "metodo": metodo})


def quien() -> dict:
    return _quien.get()


# ---------------------------------------------------------------- log en archivo
def configurar_logs() -> None:
    """Deja el log rotativo listo: logs/od.log (5 MB × 8 archivos)."""
    if _acceso.handlers:
        return
    try:
        carpeta = Path(settings.logs_dir)
        carpeta.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(carpeta / "od.log", maxBytes=5_000_000, backupCount=8, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        _acceso.addHandler(h)
        _acceso.setLevel(logging.INFO)
        _acceso.propagate = False
    except OSError as e:
        log.warning("No se pudo abrir el log en archivo: %s", e)


def linea(**kv) -> None:
    """Una línea JSON en el log del servidor."""
    if not _acceso.handlers:
        return
    kv = {"ts": ahora().isoformat(timespec="seconds") + "Z", **kv}
    try:
        _acceso.info(json.dumps(kv, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- errores
def _depurar(d) -> dict:
    """Quita lo que no debe guardarse (claves, tokens) y acorta lo largo."""
    out = {}
    for k, v in (d or {}).items():
        if _SECRETOS.search(str(k)):
            out[k] = "***"
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False, default=str)[:300]
        else:
            out[k] = str(v)[:300]
    return out


def _huella_error(origen: str, mensaje: str, traza: str, ruta: str) -> str:
    base = re.sub(r"\d+", "N", mensaje)[:160]
    ultimo = ""
    marcos = re.findall(r'File "([^"]+)", line \d+, in (\w+)', traza or "")
    if marcos:
        ultimo = "|".join(f"{Path(a).name}:{b}" for a, b in marcos[-2:])
    ruta_n = re.sub(r"\d+", "N", ruta or "")
    return hashlib.sha1(f"{origen}|{base}|{ultimo}|{ruta_n if not ultimo else ''}".encode()).hexdigest()[:20]


def registrar_error(origen: str, mensaje: str, traza: str = "", ruta: str = "", metodo: str = "", status: int = 0,
                    usuario: str | None = None, rid: str | None = None, contexto: dict | None = None,
                    nivel: str = "error") -> int:
    """Guarda un error (agrupado con sus repetidos). Devuelve su id, o 0 si no se pudo guardar."""
    try:
        q = quien()
        usuario = usuario if usuario is not None else q.get("usuario", "")
        rid = rid or request_id()
        ruta = ruta or q.get("ruta", "")
        metodo = metodo or q.get("metodo", "")
        mensaje = (mensaje or "Error sin mensaje").strip()
        huella = _huella_error(origen, mensaje, traza, ruta)
        with SessionLocal() as s:
            e = s.scalar(select(ErrorLog).where(ErrorLog.huella == huella))
            if e is None:
                e = ErrorLog(huella=huella, nivel=nivel, origen=origen, mensaje=mensaje[:400], traza=(traza or "")[-8000:],
                             ruta=ruta[:200])
                s.add(e)
                s.flush()
            else:
                e.cuenta += 1
                e.ultima = ahora()
                if e.estado == "resuelto":                 # volvió a pasar: se reabre
                    e.estado, e.nota = "nuevo", (e.nota + " · Reapareció").strip(" ·")[:400]
                if traza and not e.traza:
                    e.traza = traza[-8000:]
            s.add(ErrorOcurrencia(error_id=e.id, usuario=(usuario or "")[:40], request_id=rid or "", metodo=metodo[:8],
                                  ruta=ruta[:200], status=status,
                                  contexto=json.dumps(_depurar(contexto), ensure_ascii=False)[:2000]))
            s.commit()
            # solo se guardan las últimas 30 ocurrencias de cada error
            viejas = s.scalars(select(ErrorOcurrencia.id).where(ErrorOcurrencia.error_id == e.id)
                               .order_by(ErrorOcurrencia.id.desc()).offset(30)).all()
            if viejas:
                s.execute(delete(ErrorOcurrencia).where(ErrorOcurrencia.id.in_(viejas)))
                s.commit()
            eid = e.id
        linea(tipo="error", rid=rid, usuario=usuario, origen=origen, ruta=ruta, status=status, mensaje=mensaje[:300],
              traza=(traza or "")[-1500:])
        return eid
    except Exception as ex:  # noqa: BLE001
        log.warning("No se pudo registrar un error: %s", ex)
        return 0


def registrar_excepcion(exc: BaseException, origen: str = "servidor", **kw) -> int:
    traza = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return registrar_error(origen, f"{type(exc).__name__}: {exc}", traza=traza, **kw)


# ---------------------------------------------------------------- actividad
# (método, patrón, categoría, texto, grupo con el pedido/entrega/grupo afectado)
RUTAS = [
    ("PUT", r"^/api/pedidos/(\d+)$", "pedido", "Guardó el pedido {0}", 1),
    ("DELETE", r"^/api/pedidos/(\d+)$", "pedido", "Eliminó el pedido {0}", 1),
    ("PUT", r"^/api/entregas/([\w-]+)$", "pedido", "Guardó la entrega {0}", 1),
    ("DELETE", r"^/api/entregas/([\w-]+)$", "pedido", "Eliminó la entrega {0}", 1),
    ("POST", r"^/api/analisis/(\d+)$", "sap", "Pidió analizar el pedido {0} en SAP", 1),
    ("PUT", r"^/api/analisis/(\d+)/carga$", "pedido", "Ajustó la carga del pedido {0}", 1),
    ("POST", r"^/api/cubicaje/(\d+)$", "cubicaje", "Cubicó el pedido {0}", 1),
    ("POST", r"^/api/cubicaje-libre/desde-pedido$", "cubicaje", "Trajo un pedido al cubicador", 0),
    ("POST", r"^/api/cubicaje-libre/importar$", "cubicaje", "Importó una carga masiva al cubicador", 0),
    ("PUT", r"^/api/predistribuido/(\d+)$", "cubicaje", "Guardó el reparto del pedido {0}", 1),
    ("POST", r"^/api/predistribuido/(\d+)/importar$", "cubicaje", "Importó el reparto del pedido {0}", 1),
    ("PUT", r"^/api/ajustes-cubicaje$", "cubicaje", "Cambió los ajustes del motor de cubicaje", 0),
    ("POST", r"^/api/sap/leer_pedido$", "sap", "Pidió leer un pedido en SAP", 0),
    ("POST", r"^/api/sap/crear_entregas$", "sap", "Pidió crear entregas en SAP", 0),
    ("POST", r"^/api/sap/crear_grupo$", "sap", "Pidió crear un grupo en SAP", 0),
    ("POST", r"^/api/sap/fecha_grupo$", "sap", "Pidió poner la cita de un grupo en SAP", 0),
    ("POST", r"^/api/sap/borrar_entrega$", "sap", "Pidió borrar una entrega en SAP", 0),
    ("POST", r"^/api/sap/borrar_grupo$", "sap", "Pidió borrar un grupo en SAP", 0),
    ("POST", r"^/api/archivos$", "pedido", "Subió un archivo", 0),
    ("PATCH", r"^/api/archivos/(\d+)$", "pedido", "Cambió un archivo", 0),
    ("DELETE", r"^/api/archivos/(\d+)$", "pedido", "Borró un archivo", 0),
    ("POST", r"^/api/medidas/importar$", "datos", "Importó la Base de Medidas", 0),
    ("PUT", r"^/api/medidas/([\w-]+)$", "datos", "Editó las medidas del producto {0}", 1),
    ("PUT", r"^/api/clientes/([^/]+)$", "datos", "Cambió las reglas del cliente {0}", 1),
    ("PUT", r"^/api/conexion$", "datos", "Cambió la conexión a SQL Server", 0),
    ("POST", r"^/api/conexion/probar$", "datos", "Probó la conexión a SQL Server", 0),
    ("POST", r"^/api/bases/actualizar$", "datos", "Actualizó las bases desde SQL Server", 0),
    ("POST", r"^/api/respaldos$", "datos", "Hizo un respaldo", 0),
    ("POST", r"^/api/paquetes$", "datos", "Cargó un paquete de datos", 0),
    ("PUT", r"^/api/config/([\w:.-]+)$", "datos", "Guardó la configuración {0}", 1),
    ("GET", r"^/api/analisis/(\d+)/excel$", "pedido", "Exportó el análisis del pedido {0}", 1),
    ("GET", r"^/api/cubicaje/(\d+)/excel$", "cubicaje", "Exportó el cubicaje del pedido {0}", 1),
    ("GET", r"^/api/cubicaje-libre/excel$", "cubicaje", "Exportó el cubicaje del cubicador", 0),
]
_RUTAS = [(m, re.compile(p), c, t, g) for m, p, c, t, g in RUTAS]
SIN_REGISTRO = ("/api/cubicaje-libre", "/api/sesion", "/api/log", "/api/ping", "/api/version", "/api/estado", "/api/salud", "/api/mi", "/api/admin")


def describir(metodo: str, ruta: str):
    """(categoría, texto, entidad) de una petición, o None si no vale la pena guardarla."""
    for m, rx, cat, texto, g in _RUTAS:
        if m == metodo and (mo := rx.match(ruta)):
            ent = mo.group(g) if g else ""
            return cat, texto.format(ent) if "{0}" in texto else texto, ent
    if metodo == "POST" and ruta == "/api/cubicaje-libre":
        return None
    if metodo in ("POST", "PUT", "DELETE", "PATCH") and not ruta.startswith(SIN_REGISTRO):
        return "sistema", f"{metodo} {ruta}", ""
    return None


def registrar_actividad(usuario: str, categoria: str, accion: str, entidad: str = "", resultado: str = "ok",
                        detalle: str = "", ip: str = "", ms: int = 0, rid: str | None = None) -> None:
    try:
        with SessionLocal() as s:
            s.add(Actividad(usuario=(usuario or "")[:40], categoria=categoria[:12], accion=accion[:200], entidad=str(entidad)[:40],
                            resultado=resultado[:10], detalle=(detalle or "")[:400], ip=(ip or "")[:60], ms=int(ms),
                            request_id=(rid if rid is not None else request_id())[:16]))
            s.commit()
    except Exception as ex:  # noqa: BLE001
        log.warning("No se pudo registrar la actividad: %s", ex)


# ---------------------------------------------------------------- mantenimiento
def purgar() -> dict:
    """Borra lo que ya pasó el plazo de guardado."""
    try:
        with SessionLocal() as s:
            a = s.execute(delete(Actividad).where(Actividad.at < ahora() - timedelta(days=settings.retencion_actividad_dias))).rowcount
            lim = ahora() - timedelta(days=settings.retencion_errores_dias)
            e = s.execute(delete(ErrorLog).where(ErrorLog.estado == "resuelto", ErrorLog.ultima < lim)).rowcount
            s.commit()
            from . import seguridad
            seguridad.purgar_sesiones(s)
        return {"actividad": a or 0, "errores": e or 0}
    except Exception as ex:  # noqa: BLE001
        log.warning("No se pudo purgar el historial: %s", ex)
        return {}
