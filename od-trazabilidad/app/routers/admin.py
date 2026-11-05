"""Administración: resumen, historial por analista, errores, cuentas y estado del servidor."""
from __future__ import annotations

import csv
import io
import json
import os
import platform
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import registro, seguridad
from ..config import settings
from ..db import engine, get_session
from ..models import Actividad, ErrorLog, ErrorOcurrencia, SesionWeb, Usuario, ahora
from .cuenta import cuenta_de, fila_actividad, solo_admin

router = APIRouter(prefix="/admin", dependencies=[Depends(solo_admin)])
_INICIO = time.time()


def _iso(d: datetime | None) -> str | None:
    return d.isoformat(timespec="seconds") + "Z" if d else None


def _fecha(v: str, fin: bool = False) -> datetime | None:
    try:
        d = datetime.fromisoformat(v)
    except (TypeError, ValueError):
        return None
    if fin and len(v) <= 10:
        d += timedelta(days=1)
    return d


def _nombres(s: Session) -> dict[str, str]:
    return {u.usuario: u.nombre or u.usuario for u in s.scalars(select(Usuario)).all()}


# ---------------------------------------------------------------- resumen
@router.get("/resumen")
def resumen(horas: int = 24, s: Session = Depends(get_session)):
    horas = max(1, min(horas, 24 * 90))
    desde = ahora() - timedelta(hours=horas)
    nombres = _nombres(s)
    por_user = s.execute(select(Actividad.usuario, func.count(), func.max(Actividad.at))
                         .where(Actividad.at >= desde, Actividad.categoria != "cuenta")
                         .group_by(Actividad.usuario).order_by(func.count().desc())).all()
    por_cat = s.execute(select(Actividad.categoria, func.count()).where(Actividad.at >= desde)
                        .group_by(Actividad.categoria).order_by(func.count().desc())).all()
    # barras por tiempo: por hora si el período es corto, por día si es largo
    por_dia = horas > 48
    cubo = (lambda d: d.strftime("%Y-%m-%d")) if por_dia else (lambda d: d.strftime("%Y-%m-%d %H:00"))
    acc = {}
    for (at,) in s.execute(select(Actividad.at).where(Actividad.at >= desde, Actividad.categoria != "cuenta")).all():
        acc[cubo(at)] = acc.get(cubo(at), 0) + 1
    err = {}
    for (at,) in s.execute(select(ErrorOcurrencia.at).where(ErrorOcurrencia.at >= desde)).all():
        err[cubo(at)] = err.get(cubo(at), 0) + 1
    paso = timedelta(days=1) if por_dia else timedelta(hours=1)
    t = desde.replace(minute=0, second=0, microsecond=0, **({"hour": 0} if por_dia else {}))
    serie = []
    while t <= ahora():
        k = cubo(t)
        serie.append({"t": k.replace(" ", "T") + ("" if por_dia else ":00") + "Z" if not por_dia else k + "T00:00:00Z",
                      "acciones": acc.get(k, 0), "errores": err.get(k, 0)})
        t += paso
    en_linea = s.execute(select(Usuario.usuario, func.max(SesionWeb.vista)).join(SesionWeb, SesionWeb.usuario_id == Usuario.id)
                         .where(SesionWeb.vista >= ahora() - timedelta(minutes=30)).group_by(Usuario.usuario)).all()
    top = s.scalars(select(ErrorLog).where(ErrorLog.ultima >= desde).order_by(ErrorLog.cuenta.desc(), ErrorLog.ultima.desc()).limit(5)).all()
    fallos = s.scalar(select(func.count()).select_from(Actividad).where(Actividad.at >= desde, Actividad.resultado == "rechazada")) or 0
    return {
        "horas": horas, "por_dia": por_dia,
        "acciones": sum(n for _, n, _ in por_user),
        "analistas_activos": len(por_user),
        "errores_periodo": s.scalar(select(func.count()).select_from(ErrorOcurrencia).where(ErrorOcurrencia.at >= desde)) or 0,
        "errores_abiertos": s.scalar(select(func.count()).select_from(ErrorLog).where(ErrorLog.estado != "resuelto")) or 0,
        "errores_nuevos": s.scalar(select(func.count()).select_from(ErrorLog).where(ErrorLog.estado == "nuevo")) or 0,
        "ingresos_rechazados": fallos,
        "por_usuario": [{"usuario": u, "nombre": nombres.get(u, u), "acciones": n, "ultima": _iso(m)} for u, n, m in por_user],
        "por_categoria": [{"categoria": c, "n": n} for c, n in por_cat],
        "serie": serie,
        "en_linea": [{"usuario": u, "nombre": nombres.get(u, u), "visto": _iso(v)} for u, v in en_linea],
        "top_errores": [_error_resumen(e) for e in top],
    }


# ---------------------------------------------------------------- actividad
def _consulta_actividad(usuario: str, categoria: str, q: str, desde: str, hasta: str, resultado: str, entidad: str):
    f = []
    if usuario:
        f.append(Actividad.usuario == usuario)
    if categoria:
        f.append(Actividad.categoria == categoria)
    if resultado:
        f.append(Actividad.resultado == resultado)
    if entidad:
        f.append(Actividad.entidad == entidad)
    if q.strip():
        like = f"%{q.strip()}%"
        f.append(or_(Actividad.accion.like(like), Actividad.entidad.like(like), Actividad.detalle.like(like),
                     Actividad.request_id == q.strip()))
    if d := _fecha(desde):
        f.append(Actividad.at >= d)
    if d := _fecha(hasta, fin=True):
        f.append(Actividad.at < d)
    return f


@router.get("/actividad")
def actividad(usuario: str = "", categoria: str = "", q: str = "", desde: str = "", hasta: str = "", resultado: str = "",
              entidad: str = "", limite: int = 100, offset: int = 0, s: Session = Depends(get_session)):
    f = _consulta_actividad(usuario, categoria, q, desde, hasta, resultado, entidad)
    total = s.scalar(select(func.count()).select_from(Actividad).where(*f)) or 0
    filas = s.scalars(select(Actividad).where(*f).order_by(Actividad.at.desc(), Actividad.id.desc()).offset(max(0, offset))
                      .limit(max(1, min(limite, 500)))).all()
    nombres = _nombres(s)
    usuarios = [u for (u,) in s.execute(select(Actividad.usuario).distinct().order_by(Actividad.usuario)).all()]
    return {"total": total, "filas": [{**fila_actividad(a), "nombre": nombres.get(a.usuario, a.usuario)} for a in filas],
            "usuarios": [{"usuario": u, "nombre": nombres.get(u, u)} for u in usuarios if u]}


@router.get("/actividad.csv")
def actividad_csv(usuario: str = "", categoria: str = "", q: str = "", desde: str = "", hasta: str = "", resultado: str = "",
                  entidad: str = "", s: Session = Depends(get_session)):
    f = _consulta_actividad(usuario, categoria, q, desde, hasta, resultado, entidad)
    filas = s.scalars(select(Actividad).where(*f).order_by(Actividad.at.desc(), Actividad.id.desc()).limit(20000)).all()
    nombres = _nombres(s)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Fecha (UTC)", "Usuario", "Nombre", "Categoría", "Acción", "Entidad", "Resultado", "Detalle", "IP", "ms", "Código de petición"])
    for a in filas:
        w.writerow([a.at.isoformat(sep=" ", timespec="seconds"), a.usuario, nombres.get(a.usuario, ""), a.categoria, a.accion,
                    a.entidad, a.resultado, a.detalle, a.ip, a.ms, a.request_id])
    datos = ("﻿" + buf.getvalue()).encode("utf-8")            # con BOM: Excel respeta los acentos
    return StreamingResponse(io.BytesIO(datos), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="actividad.csv"'})


# ---------------------------------------------------------------- errores
def _error_resumen(e: ErrorLog) -> dict:
    ult = e.ocurrencias[0] if e.ocurrencias else None
    return {"id": e.id, "nivel": e.nivel, "origen": e.origen, "mensaje": e.mensaje, "ruta": e.ruta, "cuenta": e.cuenta,
            "estado": e.estado, "primera": _iso(e.primera), "ultima": _iso(e.ultima), "nota": e.nota,
            "ultimo_usuario": ult.usuario if ult else "", "ultimo_codigo": ult.request_id if ult else ""}


@router.get("/errores")
def errores(estado: str = "", origen: str = "", q: str = "", usuario: str = "", limite: int = 200, s: Session = Depends(get_session)):
    f = []
    if estado == "abiertos":
        f.append(ErrorLog.estado != "resuelto")
    elif estado:
        f.append(ErrorLog.estado == estado)
    if origen:
        f.append(ErrorLog.origen == origen)
    if q.strip():
        like = f"%{q.strip()}%"
        f.append(or_(ErrorLog.mensaje.like(like), ErrorLog.ruta.like(like), ErrorLog.traza.like(like),
                     ErrorLog.id.in_(select(ErrorOcurrencia.error_id).where(ErrorOcurrencia.request_id == q.strip()))))
    if usuario:
        f.append(ErrorLog.id.in_(select(ErrorOcurrencia.error_id).where(ErrorOcurrencia.usuario == usuario)))
    filas = s.scalars(select(ErrorLog).where(*f).order_by(ErrorLog.ultima.desc()).limit(max(1, min(limite, 500)))).all()
    cuentas = dict(s.execute(select(ErrorLog.estado, func.count()).group_by(ErrorLog.estado)).all())
    return {"filas": [_error_resumen(e) for e in filas], "cuentas": cuentas}


@router.get("/errores/{eid}")
def error_detalle(eid: int, s: Session = Depends(get_session)):
    e = s.get(ErrorLog, eid)
    if e is None:
        raise HTTPException(404, "Ese error no existe.")
    nombres = _nombres(s)
    if e.estado == "nuevo":
        e.estado = "visto"
        s.commit()
    ocs = []
    for o in e.ocurrencias:
        try:
            ctx = json.loads(o.contexto or "{}")
        except ValueError:
            ctx = {}
        # lo que esa persona hizo justo antes: el contexto para entender cómo se llegó al error
        antes = s.scalars(select(Actividad).where(Actividad.usuario == o.usuario, Actividad.at <= o.at,
                                                   Actividad.at >= o.at - timedelta(minutes=15))
                          .order_by(Actividad.id.desc()).limit(5)).all() if o.usuario else []
        ocs.append({"id": o.id, "at": _iso(o.at), "usuario": o.usuario, "nombre": nombres.get(o.usuario, o.usuario),
                    "codigo": o.request_id, "metodo": o.metodo, "ruta": o.ruta, "status": o.status, "contexto": ctx,
                    "antes": [{"at": _iso(a.at), "accion": a.accion} for a in antes]})
    return {**_error_resumen(e), "traza": e.traza, "ocurrencias": ocs}


@router.put("/errores/{eid}")
def error_actualizar(eid: int, body: dict, request: Request, s: Session = Depends(get_session)):
    e = s.get(ErrorLog, eid)
    if e is None:
        raise HTTPException(404, "Ese error no existe.")
    if body.get("estado") in ("nuevo", "visto", "resuelto"):
        e.estado = body["estado"]
    if "nota" in body:
        e.nota = str(body["nota"] or "")[:400]
    s.commit()
    c = cuenta_de(request)
    registro.registrar_actividad(c["usuario"] if c else "", "sistema", f"Marcó el error {eid} como {e.estado}", entidad=str(eid),
                                 ip=request.client.host if request.client else "")
    return _error_resumen(e)


# ---------------------------------------------------------------- cuentas
def _usuario_dict(u: Usuario, s: Session) -> dict:
    sesiones = s.scalar(select(func.count()).select_from(SesionWeb).where(SesionWeb.usuario_id == u.id)) or 0
    acciones = s.scalar(select(func.count()).select_from(Actividad).where(Actividad.usuario == u.usuario, Actividad.categoria != "cuenta")) or 0
    return {"id": u.id, "usuario": u.usuario, "nombre": u.nombre or u.usuario, "rol": u.rol, "activo": u.activo,
            "debe_cambiar_clave": u.debe_cambiar_clave, "creado": _iso(u.creado), "ultimo_acceso": _iso(u.ultimo_acceso),
            "sesiones": sesiones, "acciones": acciones}


@router.get("/usuarios")
def usuarios(s: Session = Depends(get_session)):
    filas = s.scalars(select(Usuario).order_by(Usuario.activo.desc(), Usuario.usuario)).all()
    return {"filas": [_usuario_dict(u, s) for u in filas], "modo": "cuentas" if seguridad.hay_cuentas(s, fresco=True) else "abierto"}


@router.post("/usuarios", status_code=201)
def usuario_crear(body: dict, request: Request, s: Session = Depends(get_session)):
    u = seguridad.nombre_usuario(body.get("usuario", ""))
    if not u:
        raise HTTPException(422, "Escribe un usuario (letras, números, punto o guion).")
    if s.scalar(select(Usuario).where(Usuario.usuario == u)):
        raise HTTPException(409, f"Ya existe el usuario «{u}».")
    rol = body.get("rol") if body.get("rol") in seguridad.ROLES else "analista"
    clave = str(body.get("clave") or "") or seguridad.clave_temporal()
    motivo = seguridad.validar_clave_nueva(clave, u)
    if motivo:
        raise HTTPException(422, motivo)
    fila = Usuario(usuario=u, nombre=" ".join(str(body.get("nombre") or u).split())[:60], rol=rol,
                   clave_hash=seguridad.hashear(clave), debe_cambiar_clave=True)
    s.add(fila)
    s.commit()
    seguridad.olvidar_modo()
    c = cuenta_de(request)
    registro.registrar_actividad(c["usuario"] if c else "", "cuenta", f"Creó la cuenta {u} ({rol})", entidad=u,
                                 ip=request.client.host if request.client else "")
    return {**_usuario_dict(fila, s), "clave_temporal": clave}          # única vez que se ve la clave


@router.put("/usuarios/{uid}")
def usuario_editar(uid: int, body: dict, request: Request, s: Session = Depends(get_session)):
    fila = s.get(Usuario, uid)
    if fila is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    yo = cuenta_de(request)
    admins = s.scalar(select(func.count()).select_from(Usuario).where(Usuario.rol == "admin", Usuario.activo.is_(True))) or 0
    if "nombre" in body:
        fila.nombre = " ".join(str(body["nombre"] or fila.usuario).split())[:60]
    cambios = []
    if body.get("rol") in seguridad.ROLES and body["rol"] != fila.rol:
        if fila.rol == "admin" and fila.activo and admins <= 1:
            raise HTTPException(409, "Debe quedar al menos un administrador activo.")
        cambios.append(f"rol {fila.rol} → {body['rol']}")
        fila.rol = body["rol"]
    if "activo" in body and bool(body["activo"]) != fila.activo:
        if not body["activo"]:
            if yo and yo["id"] == fila.id:
                raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
            if fila.rol == "admin" and admins <= 1:
                raise HTTPException(409, "Debe quedar al menos un administrador activo.")
            seguridad.cerrar_sesiones_de(s, fila.id)
        fila.activo = bool(body["activo"])
        cambios.append("activada" if fila.activo else "desactivada")
    s.commit()
    seguridad.olvidar_modo()
    if cambios:
        registro.registrar_actividad(yo["usuario"] if yo else "", "cuenta", f"Cambió la cuenta {fila.usuario}: " + ", ".join(cambios),
                                     entidad=fila.usuario, ip=request.client.host if request.client else "")
    return _usuario_dict(fila, s)


@router.post("/usuarios/{uid}/clave")
def usuario_resetear(uid: int, request: Request, s: Session = Depends(get_session)):
    fila = s.get(Usuario, uid)
    if fila is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    clave = seguridad.clave_temporal()
    fila.clave_hash = seguridad.hashear(clave)
    fila.debe_cambiar_clave = True
    s.commit()
    seguridad.cerrar_sesiones_de(s, fila.id)
    c = cuenta_de(request)
    registro.registrar_actividad(c["usuario"] if c else "", "cuenta", f"Restableció la clave de {fila.usuario}", entidad=fila.usuario,
                                 ip=request.client.host if request.client else "")
    return {"clave_temporal": clave}


@router.post("/usuarios/{uid}/cerrar-sesiones")
def usuario_cerrar_sesiones(uid: int, request: Request, s: Session = Depends(get_session)):
    fila = s.get(Usuario, uid)
    if fila is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    n = seguridad.cerrar_sesiones_de(s, fila.id)
    c = cuenta_de(request)
    registro.registrar_actividad(c["usuario"] if c else "", "cuenta", f"Cerró las sesiones de {fila.usuario}", entidad=fila.usuario,
                                 detalle=f"{n} sesión(es)", ip=request.client.host if request.client else "")
    return {"cerradas": n}


# ---------------------------------------------------------------- servidor
def _tamano(ruta: Path) -> int:
    try:
        if ruta.is_file():
            return ruta.stat().st_size
        return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file())
    except OSError:
        return 0


@router.get("/servidor")
def servidor(s: Session = Depends(get_session)):
    from ..integrations import bases
    url = settings.database_url
    es_sqlite = url.startswith("sqlite")
    ruta_db = Path(url.replace("sqlite:///", "")) if es_sqlite else None
    try:
        libre = shutil.disk_usage(Path(settings.logs_dir).parent if Path(settings.logs_dir).parent.exists() else ".").free
    except OSError:
        libre = 0
    try:
        base_bases = bases.estado() if hasattr(bases, "estado") else {}
    except Exception as e:  # noqa: BLE001
        base_bases = {"error": str(e)[:150]}
    return {
        "version": "2026.10", "python": sys.version.split()[0], "sistema": platform.platform(),
        "inicio": _iso(datetime.utcfromtimestamp(_INICIO)), "activo_seg": int(time.time() - _INICIO),
        "hora_servidor": _iso(ahora()), "proceso": os.getpid(),
        "base": {"tipo": engine.dialect.name, "tamano": _tamano(ruta_db) if ruta_db else None},
        "logs": {"carpeta": settings.logs_dir, "tamano": _tamano(Path(settings.logs_dir))},
        "disco_libre": libre,
        "autenticacion": "cuentas" if seguridad.hay_cuentas(s, fresco=True) else ("obligatoria" if settings.autenticacion == "obligatoria" else "abierta"),
        "cookie_segura": settings.cookie_segura, "sesion_horas": settings.sesion_horas,
        "retencion": {"actividad_dias": settings.retencion_actividad_dias, "errores_dias": settings.retencion_errores_dias},
        "sesiones": s.scalar(select(func.count()).select_from(SesionWeb)) or 0,
        "registros": {"actividad": s.scalar(select(func.count()).select_from(Actividad)) or 0,
                      "errores": s.scalar(select(func.count()).select_from(ErrorLog)) or 0},
        "bases": base_bases,
    }


@router.post("/purgar")
def purgar():
    return registro.purgar()
