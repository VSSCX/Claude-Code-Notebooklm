"""Clientes, sesión, respaldos y estado del sistema."""
import json as _json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import domain
from ..config import settings
from ..db import get_session
from ..integrations import acciones, bases, clientes as cli_mod, maestra, medidas as med_mod
from sqlalchemy import select

from ..models import Archivo, Entrega
from ..schemas import EntregaIn, PaqueteIn, PedidoIn




def _commit(s: Session):
    try:
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(409, "El registro choca con otro existente.") from e

from .comun import (AJUSTES_DEFECTO, CAMIONES_DEFECTO, CAMIONES_VISTA, _ajustes_cubicaje,
                    _aplicar_ajustes, _calefones_de, _clave_analisis, _clave_cubicaje)

router = APIRouter()

@router.get("/salud")
def salud(s: Session = Depends(get_session)):
    from ..integrations import base_medidas
    return {"ok": True, "maestra": maestra.estado(), "base_medidas": base_medidas.estado(),
            "medidas_cargadas": med_mod.estado(s)}


@router.get("/version")
def version(s: Session = Depends(get_session)):
    return {"version": domain.version(s)}


@router.put("/config/{clave}")
def put_config(clave: str, body: dict, s: Session = Depends(get_session)):
    domain.guardar_config(s, clave, body)
    _commit(s)
    return body


@router.get("/sesion")
def estado_sesion(request: Request):
    from ..usuarios import requiere_clave, sesion_valida
    return {"requiere_clave": requiere_clave(),
            "abierta": sesion_valida(request.cookies.get("sesion", "")),
            "usuario": domain.usuario_actual()}


@router.post("/sesion")
def abrir_sesion(body: dict, response: Response):
    from ..usuarios import entrar
    token = entrar(str(body.get("clave", "")), str(body.get("usuario", "")))
    response.set_cookie("sesion", token, httponly=True, samesite="lax")
    return {"ok": True, "usuario": str(body.get("usuario", "")).strip()[:40]}


@router.get("/conexion")
def get_conexion(s: Session = Depends(get_session)):
    """Datos de conexión a SQL Server de esta instalación. La clave nunca se devuelve."""
    from ..integrations import bases
    from ..models import Config
    c = s.get(Config, bases.CLAVE_CONFIG)
    d = _json.loads(c.valor) if c else {}
    desde_env = not d.get("url") and bool(settings.bases_url)
    return {"url": d.get("url") or (settings.bases_url if desde_env else ""),
            "usuario": d.get("usuario") or (settings.bases_usuario if desde_env else ""),
            "tiene_clave": bool(d.get("clave") or (settings.bases_clave if desde_env else "")),
            "desde_env": desde_env}


@router.put("/conexion")
def put_conexion(body: dict, s: Session = Depends(get_session)):
    """Guarda servidor, usuario y clave. Queda solo en la base local de este equipo."""
    from ..integrations import bases
    from ..models import Config
    c = s.get(Config, bases.CLAVE_CONFIG)
    antes = _json.loads(c.valor) if c else {}
    datos = {"url": str(body.get("url", "")).strip(),
             "usuario": str(body.get("usuario", "")).strip(),
             # si el campo va vacío se conserva la clave anterior: no se borra sin querer
             "clave": str(body.get("clave", "")) or antes.get("clave", "")}
    if not datos["usuario"]:
        datos["clave"] = ""                     # con cuenta de Windows no hace falta clave
    domain.guardar_config(s, bases.CLAVE_CONFIG, datos)
    _commit(s)
    bases.usar_conexion(datos)
    return {"ok": True, "tiene_clave": bool(datos["clave"])}


@router.post("/conexion/probar")
def probar_conexion():
    """Intenta conectarse y dice si las credenciales sirven."""
    from ..integrations import bases
    return bases.probar()


@router.get("/respaldos")
def get_respaldos():
    from ..respaldo import listar
    return {"copias": listar()}


@router.post("/respaldos")
def hacer_respaldo():
    from ..respaldo import copiar
    r = copiar("manual")
    if not r.get("ok"):
        raise HTTPException(422, r.get("motivo", "No se pudo respaldar."))
    return r


@router.get("/clientes")
def get_clientes(s: Session = Depends(get_session)):
    filas = [cli_mod.doc(c) for c in cli_mod.todos(s)]
    _commit(s)
    return {"filas": filas}


@router.put("/clientes/{nombre}")
def put_cliente(nombre: str, body: dict, s: Session = Depends(get_session)):
    try:
        c = cli_mod.guardar(s, {**body, "nombre": nombre})
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    _commit(s)
    return cli_mod.doc(c)
