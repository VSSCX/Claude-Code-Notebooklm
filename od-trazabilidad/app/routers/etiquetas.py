"""Etiquetas de los clientes (pack list): leer el archivo que manda el cliente, editarlo, bajarlo a Excel y cuadrarlo con lo despachado."""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
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
    """Lee el archivo de DIMARSA (el TXT de ancho fijo o las etiquetas ZPL del .prn) y lo devuelve como tabla."""
    datos = archivo.file.read(MAX_BYTES + 1)
    if not datos:
        raise HTTPException(422, "El archivo está vacío.")
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, "El archivo es demasiado grande para ser un archivo de etiquetas.")
    try:
        return etiquetas.leer(_texto(datos), archivo.filename or "", maestra.homologacion(etiquetas.CLIENTE_DIMARSA))
    except etiquetas.FormatoNoReconocido as e:
        raise HTTPException(422, str(e)) from e


def _filas(body: dict) -> list[dict]:
    filas = body.get("filas")
    if not isinstance(filas, list) or not filas or not all(isinstance(f, dict) for f in filas):
        raise HTTPException(422, "Falta leer primero el archivo de etiquetas.")
    return filas


@router.post("/etiquetas/dimarsa/excel")
def excel_dimarsa(body: dict):
    """La tabla (con lo que el analista haya editado) en el Excel que se usa para imprimir las etiquetas."""
    filas = _filas(body)
    archivo = str(body.get("archivo") or "")
    orden = next((str(f.get("orden_compra")) for f in filas if str(f.get("orden_compra") or "").strip()), "")
    nombre = f"Etiquetas_DIMARSA_{orden or 'sin_OC'}.xlsx"
    return Response(etiquetas.excel(filas, archivo), headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/etiquetas/dimarsa/cuadrar")
def cuadrar_dimarsa(body: dict, s: Session = Depends(get_session)):
    """Etiquetas de la tabla contra las unidades de las entregas elegidas, producto por producto."""
    filas, ents = _filas(body), body.get("entregas")
    if not isinstance(ents, list) or not ents:
        raise HTTPException(422, "Elige al menos una entrega para cuadrar.")
    numeros = [str(e).strip() for e in ents if str(e).strip()]
    reg = s.execute(
        select(Entrega.entrega, LineaEntrega.sku, LineaEntrega.qty)
        .join(LineaEntrega, LineaEntrega.entrega_id == Entrega.id)
        .where(Entrega.entrega.in_(numeros), Entrega.anulada.is_(False))).all()
    if not reg and not s.execute(select(Entrega.id).where(Entrega.entrega.in_(numeros))).first():
        raise HTTPException(404, "No encuentro esas entregas.")
    unidades: dict[str, int] = {}
    for _, sku, qty in reg:
        k = maestra._sku(sku)
        unidades[k] = unidades.get(k, 0) + int(qty or 0)
    prods = etiquetas.productos_para_cuadre(filas, maestra.homologacion(etiquetas.CLIENTE_DIMARSA))
    return etiquetas.cuadrar(prods, unidades, maestra.descripciones())
