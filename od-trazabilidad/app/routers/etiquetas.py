"""Etiquetas de los clientes (pack list): leer el archivo que manda el cliente y cuadrarlo con lo despachado."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import etiquetas
from ..db import get_session
from ..integrations import maestra
from ..models import Entrega, LineaEntrega

router = APIRouter()
MAX_BYTES = 8_000_000


def _texto(datos: bytes) -> str:
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return datos.decode(cod)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1", errors="replace")


@router.post("/etiquetas/dimarsa/analizar")
def analizar_dimarsa(archivo: UploadFile = File(...)):
    """Lee el archivo de etiquetas de DIMARSA (ZPL en .prn o .txt) y devuelve cuántas hay de cada producto."""
    datos = archivo.file.read(MAX_BYTES + 1)
    if not datos:
        raise HTTPException(422, "El archivo está vacío.")
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, "El archivo es demasiado grande para ser un archivo de etiquetas.")
    try:
        return etiquetas.analizar(_texto(datos), archivo.filename or "", maestra.homologacion(etiquetas.CLIENTE_DIMARSA))
    except etiquetas.FormatoNoReconocido as e:
        raise HTTPException(422, str(e)) from e


@router.post("/etiquetas/dimarsa/cuadrar")
def cuadrar_dimarsa(body: dict, s: Session = Depends(get_session)):
    """Etiquetas del archivo contra las unidades de las entregas elegidas, producto por producto."""
    prods, ents = body.get("productos"), body.get("entregas")
    if not isinstance(prods, list) or not prods:
        raise HTTPException(422, "Falta leer primero el archivo de etiquetas.")
    if not isinstance(ents, list) or not ents:
        raise HTTPException(422, "Elige al menos una entrega para cuadrar.")
    numeros = [str(e).strip() for e in ents if str(e).strip()]
    filas = s.execute(
        select(Entrega.entrega, LineaEntrega.sku, LineaEntrega.qty)
        .join(LineaEntrega, LineaEntrega.entrega_id == Entrega.id)
        .where(Entrega.entrega.in_(numeros), Entrega.anulada.is_(False))).all()
    if not filas and not s.execute(select(Entrega.id).where(Entrega.entrega.in_(numeros))).first():
        raise HTTPException(404, "No encuentro esas entregas.")
    unidades: dict[str, int] = {}
    for _, sku, qty in filas:
        k = maestra._sku(sku)
        unidades[k] = unidades.get(k, 0) + int(qty or 0)
    return etiquetas.cuadrar(prods, unidades, maestra.descripciones())
