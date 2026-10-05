"""Entrar, salir, cambiar la clave, ver mi historial y recibir los errores del navegador."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import domain, registro, seguridad
from ..db import get_session
from ..models import Actividad, Usuario, ahora

router = APIRouter()
_ultimos_reportes: dict[str, list[float]] = {}


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def cuenta_de(request: Request) -> dict | None:
    return getattr(request.state, "cuenta", None)


def solo_admin(request: Request, s: Session = Depends(get_session)) -> dict | None:
    """Con cuentas, solo los administradores. Sin cuentas (una persona en su PC) se deja pasar."""
    if not seguridad.exige_entrar(s):
        return None
    c = cuenta_de(request)
    if not c:
        raise HTTPException(401, "Sesión no iniciada.")
    if c["rol"] != "admin":
        raise HTTPException(403, "Esta sección es solo para administradores.")
    return c


def _cookie(response: Response, token: str) -> None:
    from ..config import settings
    response.set_cookie(seguridad.COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_segura,
                        max_age=60 * 60 * 24 * 30, path="/")


def _publico(u: Usuario) -> dict:
    return {"id": u.id, "usuario": u.usuario, "nombre": u.nombre or u.usuario, "rol": u.rol,
            "debe_cambiar_clave": bool(u.debe_cambiar_clave)}


@router.get("/sesion")
def estado_sesion(request: Request, s: Session = Depends(get_session)):
    from ..config import settings
    from ..usuarios import requiere_clave, sesion_valida
    cuentas = seguridad.hay_cuentas(s)
    c = cuenta_de(request)
    obligatoria = settings.autenticacion == "obligatoria"
    if cuentas or obligatoria:
        return {"modo": "cuentas", "abierta": bool(c), "cuenta": c, "requiere_clave": True,
                "usuario": (c or {}).get("nombre", ""),
                "configuracion_inicial": (not cuentas) and obligatoria,
                "puede_configurar": bool(request.client and request.client.host in ("127.0.0.1", "::1", "localhost"))}
    return {"modo": "abierto", "requiere_clave": requiere_clave(),
            "abierta": sesion_valida(request.cookies.get("sesion", "")),
            "usuario": domain.usuario_actual(), "cuenta": None}


@router.post("/sesion")
def abrir_sesion(body: dict, request: Request, response: Response, s: Session = Depends(get_session)):
    from ..usuarios import entrar
    if not seguridad.exige_entrar(s):                       # modo abierto: nombre (y clave de acceso si el .env la trae)
        token = entrar(str(body.get("clave", "")), str(body.get("usuario", "")))
        response.set_cookie("sesion", token, httponly=True, samesite="lax")
        return {"ok": True, "usuario": str(body.get("usuario", "")).strip()[:40]}
    u = seguridad.nombre_usuario(body.get("usuario", ""))
    clave = str(body.get("clave", ""))
    ip = _ip(request)
    if not u or not clave:
        raise HTTPException(422, "Escribe tu usuario y tu clave.")
    espera = seguridad.segundos_bloqueado(u, ip)
    if espera:
        registro.registrar_actividad(u, "cuenta", "Intento de ingreso bloqueado", resultado="rechazada",
                                     detalle=f"Demasiados intentos. Espera {espera} s.", ip=ip)
        raise HTTPException(429, f"Demasiados intentos. Vuelve a intentar en {max(1, espera // 60 + (1 if espera % 60 else 0))} min.")
    fila = s.scalar(select(Usuario).where(Usuario.usuario == u))
    if fila is None or not fila.activo or not seguridad.verificar(clave, fila.clave_hash):
        quedan = seguridad.anotar_fallo(u, ip)
        registro.registrar_actividad(u, "cuenta", "Intento de ingreso fallido", resultado="rechazada",
                                     detalle="Usuario o clave incorrectos" + ("" if quedan else " · cuenta bloqueada 5 min"), ip=ip)
        raise HTTPException(401, "Usuario o clave incorrectos." + (f" Te quedan {quedan} intentos." if 0 < quedan <= 2 else ""))
    seguridad.limpiar_fallos(u, ip)
    token = seguridad.abrir_sesion(s, fila, ip, request.headers.get("user-agent", ""))
    _cookie(response, token)
    registro.registrar_actividad(fila.usuario, "cuenta", "Inició sesión", ip=ip)
    return {"ok": True, "cuenta": _publico(fila), "usuario": fila.nombre or fila.usuario}


@router.delete("/sesion")
def cerrar_sesion(request: Request, response: Response, s: Session = Depends(get_session)):
    token = request.cookies.get(seguridad.COOKIE, "")
    c = cuenta_de(request)
    if token:
        seguridad.cerrar_sesion(s, token)
    if c:
        registro.registrar_actividad(c["usuario"], "cuenta", "Cerró sesión", ip=_ip(request))
    response.delete_cookie(seguridad.COOKIE, path="/")
    return {"ok": True}


@router.post("/sesion/clave")
def cambiar_clave(body: dict, request: Request, response: Response, s: Session = Depends(get_session)):
    c = cuenta_de(request)
    if not c:
        raise HTTPException(401, "Sesión no iniciada.")
    fila = s.get(Usuario, c["id"])
    if not seguridad.verificar(str(body.get("actual", "")), fila.clave_hash):
        raise HTTPException(422, "La clave actual no coincide.")
    nueva = str(body.get("nueva", ""))
    motivo = seguridad.validar_clave_nueva(nueva, fila.usuario)
    if motivo:
        raise HTTPException(422, motivo)
    if seguridad.verificar(nueva, fila.clave_hash):
        raise HTTPException(422, "La clave nueva debe ser distinta de la actual.")
    fila.clave_hash = seguridad.hashear(nueva)
    fila.debe_cambiar_clave = False
    s.commit()
    cerradas = seguridad.cerrar_sesiones_de(s, fila.id, salvo=request.cookies.get(seguridad.COOKIE, ""))
    registro.registrar_actividad(fila.usuario, "cuenta", "Cambió su clave", detalle=f"{cerradas} sesión(es) cerradas" if cerradas else "", ip=_ip(request))
    return {"ok": True}


@router.post("/sesion/configuracion-inicial")
def configuracion_inicial(body: dict, request: Request, response: Response, s: Session = Depends(get_session)):
    """La primera cuenta (administrador) de un servidor que todavía no tiene ninguna. Solo desde el propio servidor."""
    if seguridad.hay_cuentas(s, fresco=True):
        raise HTTPException(409, "Ya hay cuentas creadas.")
    if not (request.client and request.client.host in ("127.0.0.1", "::1", "localhost")):
        raise HTTPException(403, "La primera cuenta se crea desde el propio servidor (o con ADMIN_INICIAL en el .env).")
    return _crear_primera(body, request, response, s)


def _crear_primera(body: dict, request: Request, response: Response, s: Session):
    u = seguridad.nombre_usuario(body.get("usuario", ""))
    nombre = " ".join(str(body.get("nombre", "")).split())[:60] or u
    clave = str(body.get("clave", ""))
    if not u:
        raise HTTPException(422, "Escribe un usuario (letras, números, punto o guion).")
    motivo = seguridad.validar_clave_nueva(clave, u)
    if motivo:
        raise HTTPException(422, motivo)
    fila = Usuario(usuario=u, nombre=nombre, rol="admin", clave_hash=seguridad.hashear(clave))
    s.add(fila)
    s.commit()
    seguridad.olvidar_modo()
    token = seguridad.abrir_sesion(s, fila, _ip(request), request.headers.get("user-agent", ""))
    _cookie(response, token)
    registro.registrar_actividad(fila.usuario, "cuenta", "Creó la primera cuenta (administrador)", ip=_ip(request))
    return {"ok": True, "cuenta": _publico(fila)}


@router.get("/mi/actividad")
def mi_actividad(request: Request, limite: int = 100, desde: str = "", s: Session = Depends(get_session)):
    """Lo que hice yo: mismo historial que ve el administrador, pero solo el propio."""
    c = cuenta_de(request)
    yo = c["usuario"] if c else domain.usuario_actual()
    q = select(Actividad).where(Actividad.usuario == yo).order_by(Actividad.id.desc())
    if desde:
        try:
            from datetime import datetime
            q = q.where(Actividad.at >= datetime.fromisoformat(desde))
        except ValueError:
            pass
    filas = s.scalars(q.limit(max(1, min(limite, 500)))).all()
    total = s.scalar(select(func.count()).select_from(Actividad).where(Actividad.usuario == yo)) or 0
    return {"usuario": yo, "total": total, "filas": [fila_actividad(a) for a in filas]}


def fila_actividad(a: Actividad) -> dict:
    return {"id": a.id, "at": a.at.isoformat(timespec="seconds") + "Z", "usuario": a.usuario, "categoria": a.categoria,
            "accion": a.accion, "entidad": a.entidad, "resultado": a.resultado, "detalle": a.detalle, "ip": a.ip,
            "ms": a.ms, "request_id": a.request_id}


@router.post("/log/cliente")
def log_cliente(body: dict, request: Request):
    """Los errores que se ven en el navegador (una pantalla en blanco, un fallo de red) también quedan registrados."""
    ip = _ip(request)
    t = time.time()
    lista = [x for x in _ultimos_reportes.get(ip, []) if t - x < 60]
    if len(lista) >= 20:                                   # un navegador en bucle no debe llenar el registro
        return {"ok": False, "limitado": True}
    lista.append(t)
    _ultimos_reportes[ip] = lista
    c = cuenta_de(request)
    quien = c["usuario"] if c else domain.usuario_actual()
    ctx = {"vista": body.get("vista"), "pagina": body.get("url"), "navegador": request.headers.get("user-agent", "")[:120],
           **(body.get("extra") if isinstance(body.get("extra"), dict) else {})}
    eid = registro.registrar_error("navegador", str(body.get("mensaje") or "Error en el navegador")[:400],
                                   traza=str(body.get("pila") or "")[:6000], ruta=str(body.get("url") or "")[:200],
                                   metodo="", usuario=quien, contexto=ctx)
    return {"ok": True, "id": eid, "codigo": registro.request_id()}
