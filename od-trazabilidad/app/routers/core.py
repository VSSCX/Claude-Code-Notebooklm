"""Pedidos, entregas y bandeja."""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
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

from .comun import (AJUSTES_DEFECTO, CAMIONES_DEFECTO, CAMIONES_VISTA, _ajustes_cubicaje,
                    _aplicar_ajustes, _calefones_de, _clave_analisis, _clave_cubicaje, _sop_de)

router = APIRouter()

@router.get("/estado")
def estado(s: Session = Depends(get_session)):
    # ya son tipos simples: se serializa directo, sin pasar por jsonable_encoder (con miles de filas pesa más que la consulta)
    return JSONResponse(domain.estado(s))


@router.put("/pedidos/{numero}")
def put_pedido(numero: str, body: PedidoIn, s: Session = Depends(get_session)):
    if body.pedido != numero:
        raise HTTPException(422, "El número de pedido no coincide con la URL.")
    p = domain.guardar_pedido(s, body)
    _commit(s)
    s.refresh(p)
    return domain.pedido_doc(p)


@router.delete("/pedidos/{numero}", status_code=204)
def delete_pedido(numero: str, s: Session = Depends(get_session)):
    if not domain.borrar_pedido(s, numero):
        raise HTTPException(404, "Pedido no encontrado.")
    _commit(s)


@router.put("/entregas/{numero}")
def put_entrega(numero: str, body: EntregaIn, s: Session = Depends(get_session)):
    if body.entrega != numero:
        raise HTTPException(422, "El número de entrega no coincide con la URL.")
    try:
        e = domain.guardar_entrega(s, body)
    except domain.ErrorNegocio as err:
        s.rollback()
        raise HTTPException(422, str(err)) from err
    _commit(s)
    s.refresh(e)
    return domain.entrega_doc(e)


@router.delete("/entregas/{numero}", status_code=204)
def delete_entrega(numero: str, s: Session = Depends(get_session)):
    if not domain.borrar_entrega(s, numero):
        raise HTTPException(404, "Entrega no encontrada.")
    _commit(s)


@router.get("/patron")
def get_patron(cliente: str = "", s: Session = Depends(get_session)):
    return domain.patron(s, cliente.upper())


@router.get("/plan/{numero}")
def get_plan(numero: str, refrescar: bool = False, s: Session = Depends(get_session)):
    """Plan SOP, saldo y disponibilidad para los productos de un pedido."""
    p = domain._get_pedido(s, numero)
    if p is None:
        raise HTTPException(404, "Pedido no encontrado.")
    grupo, _codigo = _sop_de(p.cliente, s)
    if refrescar:
        bases.limpiar_cache()
    try:
        plan = bases.plan_sop(grupo)
        disp = bases.disponibilidad()
    except Exception as e:  # noqa: BLE001 - se informa en pantalla, no rompe el pedido
        return {"ok": False, "error": str(e)[:300], "grupo": grupo, "productos": {}}
    productos = {}
    for l in p.lineas:
        sku = domain.norm_sku(l.sku)
        productos[sku] = {"plan": plan.get(sku), "disponible": disp.get(sku)}
    tipos = {v["tipo"] for v in plan.values()}
    return {"ok": True, "grupo": grupo, "tipo_plan": ", ".join(sorted(tipos)),
            "grupo_encontrado": bool(plan), "productos": productos}


# ---------------------------------------------------------------------------
# Análisis del pedido en un clic: VL01N + ZSD001_03 + cálculo + MMBE
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Base de Medidas cargada en la plataforma
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Cubicaje propio (port del cubicador del Excel)
# ---------------------------------------------------------------------------


# Valores calibrados contra la columna Máx Pallet de EasyCargo (467 de 545 exactos)
# Calibrado contra la columna Máx Pallet de EasyCargo: 543 de 545 productos exactos


# ---------------------------------------------------------------------------
# Cubicador libre: sin pedido, para armar y probar cargas a mano
# ---------------------------------------------------------------------------


@router.patch("/archivos/{aid}")
def asignar_archivo(aid: int, body: dict, s: Session = Depends(get_session)):
    a = domain.asignar_archivo(s, aid, str(body.get("grupo", "")).strip()[:20])
    if a is None:
        raise HTTPException(404, "Archivo no encontrado.")
    _commit(s)
    return {"id": a.id, "grupo": a.grupo}


@router.get("/pedidos-sap")
def buscar_pedido_sap(q: str = ""):
    """Busca un pedido por su número o por la orden de compra (tabla de pedidos ingresados)."""
    try:
        return {"ok": True, "resultados": bases.buscar_pedido(q)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200], "resultados": []}


@router.post("/archivos", status_code=201)
def subir_archivo(pedido: str = Form(""), grupo: str = Form(""), tipo: str = Form("adjunto"),
                  file: UploadFile = File(...), s: Session = Depends(get_session)):
    if tipo not in ("pdf", "adjunto", "visor"):
        raise HTTPException(422, "Tipo de archivo no permitido.")
    sufijo = Path(file.filename or "").suffix.lower()
    if sufijo not in (".pdf", ".html", ".png", ".jpg", ".xlsx", ".csv"):
        raise HTTPException(422, "Formato no permitido (PDF, HTML, PNG, JPG, XLSX o CSV).")
    acciones.DIR_ARCHIVOS.mkdir(parents=True, exist_ok=True)
    nombre_fs = f"{tipo}_{uuid.uuid4().hex[:8]}{sufijo}"
    destino = acciones.DIR_ARCHIVOS / nombre_fs
    with destino.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    a = domain.registrar_archivo(s, pedido, grupo, tipo, file.filename or nombre_fs, nombre_fs)
    _commit(s)
    s.refresh(a)
    return domain.archivo_doc(a, pedido)


@router.delete("/archivos/{aid}", status_code=204)
def borrar_archivo(aid: int, s: Session = Depends(get_session)):
    a = s.get(Archivo, aid)
    if a is None:
        raise HTTPException(404, "Archivo no encontrado.")
    (acciones.DIR_ARCHIVOS / a.archivo).unlink(missing_ok=True)
    s.delete(a)
    _commit(s)
