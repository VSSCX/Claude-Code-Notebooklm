"""Reparto por sucursal (predistribuido) de un pedido."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ... import domain
from ...db import get_session
from ...integrations import medidas as med_mod
from ._comun import _commit

router = APIRouter()


def _clave_predist(pedido: str) -> str:
    return f"predist:{pedido}"


PREDIST_COLS = ["Sucursal", "SKU", "Unidades", "Unidades por bulto (opcional)"]


def _conocidos(s: Session) -> set[str]:
    return {m[0].lower() for m in med_mod.filas_para_cubicaje(s)}


def _fila_predist(n: int, suc, sku, cant, bulto=None) -> tuple[dict | None, str | None]:
    """Valida una fila del reparto. Mismas reglas para el texto pegado y para el Excel.
    Devuelve (fila, None), (None, error) o (None, None) si la fila se ignora."""
    suc = str(suc if suc is not None else "").strip().upper()
    sku = domain.norm_sku(sku)
    if not suc or not sku:
        return None, f"fila {n}: faltan datos (sucursal, SKU y unidades)"
    if isinstance(cant, (int, float)):
        unidades = float(cant)
    else:
        try:
            unidades = float(str(cant).strip().replace(".", "").replace(",", "."))
        except ValueError:
            return None, f"fila {n}: '{cant}' no es una cantidad"
    if unidades <= 0:
        return None, None
    por_bulto = 0
    if bulto not in (None, ""):
        try:
            por_bulto = int(float(str(bulto).replace(",", ".")))
        except ValueError:
            return None, f"fila {n}: '{bulto}' no es una cantidad por bulto"
    return {"sucursal": suc, "sku": sku, "unidades": unidades, "por_bulto": max(0, por_bulto)}, None


def _guardar_predist(s: Session, numero: str, filas: list, errores: list) -> dict:
    doc = {"pedido": numero, "filas": filas, "errores": errores,
           "sucursales": sorted({f["sucursal"] for f in filas}),
           "unidades": sum(f["unidades"] for f in filas)}
    domain.guardar_config(s, _clave_predist(numero), doc)
    _commit(s)
    return doc


# Va antes de /predistribuido/{numero}: si no, "plantilla" se toma como número de pedido.
@router.get("/predistribuido/plantilla")
def plantilla_predistribuido():
    """Excel para cargar el reparto por sucursal de un pedido predistribuido."""
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Predistribuido"
    ws.append(PREDIST_COLS)
    ws.append(["SUC-01", "900081624", 20, None])
    ws.append(["SUC-02", "900081624", 10, None])
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1A2B4A")
        celda.alignment = Alignment(horizontal="center")
    for col, ancho in zip("ABCD", (18, 16, 12, 30)):
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = "A2"

    ayuda = wb.create_sheet("Cómo se usa")
    for linea in [
        ["Reparto por sucursal (pedidos predistribuidos)"],
        [""],
        ["1. Una fila por cada sucursal y producto, en la hoja Predistribuido."],
        ["2. Si un producto va a varias sucursales, repítelo en una fila por sucursal."],
        ["3. Unidades: cuántas van a esa sucursal. Las filas en 0 o vacías se ignoran."],
        ["4. Unidades por bulto: solo si el cliente arma bultos propios (SDA Predistribuido)."],
        ["   Déjala vacía para usar la caja del producto."],
        [""],
        ["Al importar, este reparto reemplaza al que tenía el pedido."],
        ["Si la suma de una sucursal supera la carga del análisis, se carga hasta ese tope."],
        ["Las filas de ejemplo se pueden borrar."],
    ]:
        ayuda.append(linea)
    ayuda.column_dimensions["A"].width = 90
    ayuda["A1"].font = Font(bold=True, size=13)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_predistribuido.xlsx"'})


@router.post("/predistribuido/{numero}/importar")
def importar_predistribuido(numero: str, file: UploadFile = File(...),
                            s: Session = Depends(get_session)):
    """Carga masiva del reparto: la plantilla o el archivo del cliente. Reemplaza el reparto del pedido."""
    from ... import cargas
    try:
        lec = cargas.leer_carga(file.file.read(), file.filename or "", _conocidos(s),
                                obligatorios=("sucursal", "sku", "unidades"), hojas_preferidas=("predistribuido", "carga"),
                                orden_plantilla=("sucursal", "sku", "unidades", "bulto"))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    filas = [{"sucursal": f.sucursal, "sku": f.sku, "unidades": f.qty, "por_bulto": f.bulto} for f in lec.filas]
    if not filas:
        raise HTTPException(422, "El archivo no trae filas de reparto válidas. " + "; ".join(lec.errores[:3]))
    doc = _guardar_predist(s, numero, filas, lec.errores)
    doc["lectura"] = lec.resumen()
    return doc


@router.get("/predistribuido/{numero}")
def get_predistribuido(numero: str, s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    c = s.get(Config, _clave_predist(numero))
    return _json.loads(c.valor) if c else {"filas": []}


@router.put("/predistribuido/{numero}")
def put_predistribuido(numero: str, body: dict, s: Session = Depends(get_session)):
    """Tabla de reparto por sucursal: se pega desde el archivo del cliente."""
    import re as _re
    filas = []
    errores = []
    for i, linea in enumerate(str(body.get("texto", "")).splitlines(), 1):
        if not linea.strip():
            continue
        partes = [x.strip() for x in _re.split(r"\t|;|,", linea)]
        partes = [x for x in partes if x != ""]
        if len(partes) < 3:
            errores.append(f"línea {i}: faltan datos (sucursal, SKU y unidades)")
            continue
        if partes[0].lower() in ("sucursal", "suc"):    # encabezado pegado por error
            continue
        f, error = _fila_predist(i, partes[0], partes[1], partes[-1])
        if error:
            errores.append(error.replace("fila", "línea", 1))
        elif f:
            filas.append(f)
    return _guardar_predist(s, numero, filas, errores)
