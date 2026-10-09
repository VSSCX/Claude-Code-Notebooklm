"""Base de Medidas, ajustes del cubicaje y medidas de los camiones."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ... import domain
from ...db import get_session
from ...integrations import medidas as med_mod
from ..comun import CAMIONES_BASE, LIMITES_CAMION, _ajustes_cubicaje, medidas_camiones
from ._comun import _commit

router = APIRouter()


@router.get("/medidas")
def get_medidas(buscar: str = "", limite: int = 50, s: Session = Depends(get_session)):
    from sqlalchemy import or_
    from sqlalchemy import select as _sel

    from ...models import Medida
    q = _sel(Medida)
    if buscar:
        p = f"%{buscar.strip()}%"
        q = q.where(or_(Medida.sku.like(p), Medida.descripcion.like(p)))
    filas = s.scalars(q.order_by(Medida.sku).limit(max(1, min(limite, 500)))).all()
    return {**med_mod.estado(s), "filas": [
        {"sku": m.sku, "descripcion": m.descripcion, "piezas": m.piezas, "largo": m.largo,
         "ancho": m.ancho, "alto": m.alto, "peso": m.peso, "apilar": m.apilar,
         "inclinar": m.inclinar, "rotar": m.rotar, "max_camion": m.max_camion,
         "max_pallet": m.max_pallet, "actualizado": domain._iso(m.actualizado)} for m in filas]}


@router.post("/medidas/importar")
def importar_medidas(file: UploadFile = File(...), s: Session = Depends(get_session)):
    """Carga masiva desde Base de Medidas.xlsm: agrega los nuevos y actualiza los cambiados."""
    if Path(file.filename or "").suffix.lower() not in (".xlsm", ".xlsx"):
        raise HTTPException(422, "El archivo debe ser .xlsm o .xlsx")
    try:
        filas = med_mod.leer_archivo(file.file)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"No se pudo leer el archivo: {str(e)[:200]}") from e
    if not filas:
        raise HTTPException(422, "No se encontró la hoja 'Base para carga' con sus encabezados.")
    r = med_mod.importar(s, filas)
    _commit(s)
    return {**r.__dict__, **med_mod.estado(s)}


@router.put("/medidas/{sku}")
def put_medida(sku: str, body: dict, s: Session = Depends(get_session)):
    """Corrección puntual de un producto (por ejemplo, uno que falta y frena el cubicaje)."""
    fila = {"Grupo": sku, "Descripción": body.get("descripcion"), "Piezas": body.get("piezas"),
            "Longitud": body.get("largo"), "Anchura": body.get("ancho"), "Altura": body.get("alto"),
            "Peso total": body.get("peso"), "Apilar": body.get("apilar"),
            "Inclinar": body.get("inclinar"), "Rotar": body.get("rotar"),
            "Máx Camión": body.get("max_camion"), "Máx Pallet": body.get("max_pallet")}
    r = med_mod.importar(s, [fila])
    if r.ignorados:
        raise HTTPException(422, "Largo, ancho y alto tienen que ser mayores que cero.")
    _commit(s)
    return get_medidas(buscar=sku, s=s)


@router.get("/ajustes-cubicaje")
def get_ajustes_cubicaje(s: Session = Depends(get_session)):
    return _ajustes_cubicaje(s)


@router.put("/ajustes-cubicaje")
def put_ajustes_cubicaje(body: dict, s: Session = Depends(get_session)):
    orient = str(body.get("orientacion_pallet", "largo")).lower()
    if orient not in ("excel", "largo"):
        raise HTTPException(422, "Orientación no válida (largo o excel).")
    celda = int(body.get("celda_cm") or 1)
    if celda not in (1, 2):
        raise HTTPException(422, "La precisión tiene que ser 1 o 2 cm.")
    cap = str(body.get("capacidad_pallet", "geometria")).lower()
    if cap not in ("geometria", "tabla"):
        raise HTTPException(422, "Capacidad no válida (geometria o tabla).")
    datos = {"orientacion_pallet": orient, "celda_cm": celda, "capacidad_pallet": cap,
             "kits_mezclar": bool(body["kits_mezclar"]) if "kits_mezclar" in body
             else bool(_ajustes_cubicaje(s).get("kits_mezclar", False))}
    cam = body.get("camiones")
    if cam is None:
        datos["camiones"] = medidas_camiones(s)                      # no se pisan las medidas al cambiar otro ajuste
    else:
        datos["camiones"] = _validar_camiones(cam)
    domain.guardar_config(s, "ajustes_cubicaje", datos)
    _commit(s)
    return _ajustes_cubicaje(s)


NOMBRES_CAMION = {"rampla": "la Rampla 53", "camion50": "el Camión 50"}


def _validar_camiones(cam) -> dict:
    """Medidas de los vehículos en cm. Cada campo se valida con su rango: un cero o un número de más no debe llegar al motor."""
    if not isinstance(cam, dict):
        raise HTTPException(422, "Medidas de camiones no válidas.")
    out = {}
    for clave in CAMIONES_BASE:
        g = cam.get(clave) or {}
        out[clave] = {}
        for campo, (lo, hi) in LIMITES_CAMION.items():
            try:
                v = float(str(g.get(campo)).replace(",", "."))
            except (TypeError, ValueError):
                raise HTTPException(422, f"Falta el {campo} de {NOMBRES_CAMION[clave]}.") from None
            if not lo <= v <= hi:
                raise HTTPException(422, f"El {campo} de {NOMBRES_CAMION[clave]} debe estar entre {lo * 10:.0f} y {hi * 10:.0f} mm.")
            out[clave][campo] = round(v, 1)
    return out


@router.get("/medidas/sugerir")
def sugerir_medidas(q: str = "", s: Session = Depends(get_session)):
    """Autocompletar de SKU: devuelve el producto y, si existe, su caja master."""
    from sqlalchemy import or_
    from sqlalchemy import select as _sel

    from ...models import Medida
    t = str(q or "").strip()
    if len(t) < 2:
        return {"sugerencias": []}
    p = f"%{t}%"
    filas = s.scalars(_sel(Medida).where(or_(Medida.sku.like(p), Medida.descripcion.like(p)))
                      .order_by(Medida.sku).limit(15)).all()
    por_sku = {m.sku: m for m in filas}
    # se agregan las cajas master de los SKU encontrados aunque no coincidan con el texto
    cajas = s.scalars(_sel(Medida).where(Medida.sku.in_([f"C{m.sku}" for m in filas
                                                         if not m.sku.startswith("C")]))).all()
    out = []
    for m in list(filas) + list(cajas):
        if m.sku in [x["sku"] for x in out]:
            continue
        es_caja = m.sku.startswith("C") and m.sku[1:] in por_sku
        out.append({"sku": m.sku, "descripcion": m.descripcion, "piezas": m.piezas,
                    "caja_master": es_caja or m.piezas > 1,
                    "medidas": f"{m.largo:g} × {m.ancho:g} × {m.alto:g} cm",
                    "max_camion": m.max_camion, "max_pallet": m.max_pallet})
    return {"sugerencias": out[:20]}
