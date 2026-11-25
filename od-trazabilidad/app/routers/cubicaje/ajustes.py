"""Ajustes a mano del cubicaje: lo que el analista deja en el visor 3D se guarda y las cargas de cada camión se rehacen de ahí."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import domain
from ...cubicaje import ajustes_manuales
from ...db import get_session
from ...models import Config
from ..comun import _clave_cubicaje
from ._comun import _commit, _datos_visor, _escribir_visor
from .pedido import _nombre_visor_pedido

router = APIRouter()


def _visor_valido(body: dict) -> str:
    visor = body.get("visor")
    if not isinstance(visor, str) or not visor.strip():
        raise HTTPException(422, "Falta el visor ajustado.")
    try:
        d = json.loads(visor)
    except ValueError as e:
        raise HTTPException(422, "El visor ajustado no es válido.") from e
    if not isinstance(d, dict) or not d.get("camiones"):
        raise HTTPException(422, "El visor ajustado no trae camiones.")
    return visor


@router.post("/cubicaje/{numero}/ajustes")
def ajustar_cubicaje_de_pedido(numero: str, body: dict, s: Session = Depends(get_session)):
    """Guarda el visor ajustado a mano de un pedido y rehace sus cargas por camión (lo que usan las entregas y los Excel)."""
    visor = _visor_valido(body)
    c = s.get(Config, _clave_cubicaje(numero))
    if c is None:
        raise HTTPException(404, "Este pedido todavía no está cubicado.")
    doc = json.loads(c.valor)
    if doc.get("conjunto"):
        raise HTTPException(422, "Un cubicaje conjunto todavía no se puede ajustar a mano: las cargas se reparten entre varios pedidos.")
    nombre = _nombre_visor_pedido(numero, int(doc.get("suministro") or 1))
    try:
        ajustes_manuales.aplicar(doc, _datos_visor(f"{nombre}_datos"), visor)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    _escribir_visor(nombre, visor, doc)
    domain.guardar_config(s, _clave_cubicaje(numero), doc)
    domain.anotar_flujo(s, numero, cubicaje=domain.resumen_cubicaje(doc))
    _commit(s)
    doc["visor_json"] = visor
    return doc


@router.post("/cubicaje-libre/ajustes")
def ajustar_cubicaje_libre(body: dict, s: Session = Depends(get_session)):
    """Lo mismo para el cubicador libre."""
    visor = _visor_valido(body)
    c = s.get(Config, "cubicaje_libre")
    doc = json.loads(c.valor) if c else {}
    if not doc.get("camiones"):
        raise HTTPException(404, "No hay un cubicaje que ajustar.")
    if doc.get("vista") == "pallet":
        raise HTTPException(422, "Un pallet suelto no se ajusta a mano: cambia a la vista del camión.")
    try:
        ajustes_manuales.aplicar(doc, _datos_visor("libre_datos"), visor)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    _escribir_visor("libre", visor, doc)
    domain.guardar_config(s, "cubicaje_libre", doc)
    _commit(s)
    doc["visor_json"] = visor
    return doc
