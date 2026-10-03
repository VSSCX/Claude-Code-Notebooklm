"""Ayudantes compartidos por los routers: claves de configuración y ajustes del motor."""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import domain
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


def _clave_analisis(pedido: str) -> str:
    return f"analisis:{pedido}"


def _calefones_de(cliente: str, s: Session = None) -> set:
    """El cliente marcado con "calefones aparte" trae su lista desde SQL Server."""
    regla = cli_mod.buscar(s, cliente) if s is not None else None
    aparte = regla.calefon_aparte if regla is not None else ("HITES" in (cliente or "").upper())
    if not aparte:
        return set()
    try:
        return bases.calefones()
    except Exception:  # noqa: BLE001
        return set()


AJUSTES_DEFECTO = {"orientacion_pallet": "largo", "celda_cm": 1, "capacidad_pallet": "geometria"}


def _ajustes_cubicaje(s: Session) -> dict:
    import json as _json
    from ..models import Config
    c = s.get(Config, "ajustes_cubicaje")
    return {**AJUSTES_DEFECTO, **(_json.loads(c.valor) if c else {})}


def _aplicar_ajustes(s: Session) -> dict:
    """Deja el motor con la precisión elegida antes de cubicar."""
    from ..cubicaje.core import usar_celda
    a = _ajustes_cubicaje(s)
    usar_celda(float(a.get("celda_cm") or 2))
    return a


CAMIONES_VISTA = {
    "rampla": ("Rampla 53", 1540.0, 245.0, 230.0),
    "camion50": ("Camion 50", 620.0, 244.0, 230.0),
    "pallet": ("Pallet", 0.0, 0.0, 0.0),        # se reemplaza por el pallet del cliente
}


CAMIONES_DEFECTO = [["Camion 50", 620, 244, 230], ["Rampla 53", 1540, 245, 230]]


def _clave_cubicaje(pedido: str) -> str:
    return f"cubicaje:{pedido}"
