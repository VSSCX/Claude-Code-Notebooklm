"""Base de Medidas cargada en la plataforma.

La fuente sigue siendo el archivo "Base de Medidas.xlsm" (hoja "Base para carga"),
pero se importa una vez y queda guardada. Cada importación agrega los productos
nuevos y actualiza los que cambiaron; nada se borra salvo que se pida.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Medida, ahora

CABECERA = ("Grupo", "Descripción", "Piezas", "Longitud", "Anchura", "Altura", "Peso total",
            "Apilar", "Inclinar", "Rotar", "Máx Camión", "Máx Pallet")


def norm_sku(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"^0+(?=\d)", "", str(v).strip())


def _num(v, entero=False):
    try:
        f = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return 0 if entero else 0.0
    return int(round(f)) if entero else f


def _yn(v) -> str:
    return "Y" if str(v or "").strip().upper().startswith("Y") else "N"


@dataclass
class Resumen:
    nuevos: int = 0
    duplicados: int = 0
    actualizados: int = 0
    sin_cambios: int = 0
    ignorados: int = 0
    total_archivo: int = 0
    ejemplos_ignorados: list = None


def leer_archivo(ruta_o_buffer) -> list[dict]:
    """Lee la hoja 'Base para carga' y devuelve las filas con medidas válidas."""
    from openpyxl import load_workbook
    wb = load_workbook(ruta_o_buffer, read_only=True, data_only=True)
    try:
        ws = wb["Base para carga"] if "Base para carga" in wb.sheetnames else wb.worksheets[0]
        filas, cab = [], None
        for f in ws.iter_rows(values_only=True):
            valores = list(f[:12]) + [None] * max(0, 12 - len(f))
            textos = [str(c).strip() if c is not None else "" for c in valores]
            if cab is None:
                if "Grupo" in textos and "Máx Camión" in textos:
                    cab = textos
                continue
            filas.append(dict(zip(CABECERA, valores)))
        return filas
    finally:
        wb.close()


def importar(s: Session, filas: list[dict]) -> Resumen:
    r = Resumen(total_archivo=len(filas), ejemplos_ignorados=[])
    actuales = {m.sku: m for m in s.scalars(select(Medida)).all()}
    vistos: set[str] = set()
    for f in filas:
        sku = norm_sku(f.get("Grupo"))
        largo, ancho, alto = (_num(f.get("Longitud")), _num(f.get("Anchura")), _num(f.get("Altura")))
        if not sku:
            continue                       # filas vacías o de unidades: no son productos
        if largo <= 0 or ancho <= 0 or alto <= 0:
            r.ignorados += 1               # producto sin medidas: se informa y no se carga
            if len(r.ejemplos_ignorados) < 10:
                r.ejemplos_ignorados.append(sku)
            continue
        datos = dict(descripcion=str(f.get("Descripción") or "").strip()[:150],
                     piezas=max(_num(f.get("Piezas"), True), 1),
                     largo=largo, ancho=ancho, alto=alto, peso=_num(f.get("Peso total")),
                     apilar=_yn(f.get("Apilar")), inclinar=_yn(f.get("Inclinar")),
                     rotar=_yn(f.get("Rotar")), max_camion=_num(f.get("Máx Camión"), True),
                     max_pallet=_num(f.get("Máx Pallet"), True))
        if sku in vistos:
            r.duplicados += 1              # igual que el Excel: manda la primera aparición
            continue
        vistos.add(sku)
        m = actuales.get(sku)
        if m is None:
            s.add(Medida(sku=sku, actualizado=ahora(), **datos))
            r.nuevos += 1
        elif any(getattr(m, k) != v for k, v in datos.items()):
            for k, v in datos.items():
                setattr(m, k, v)
            m.actualizado = ahora()
            r.actualizados += 1
        else:
            r.sin_cambios += 1
    return r


def filas_para_cubicaje(s: Session) -> list[list]:
    """Mismas columnas A..L que espera el cubicador."""
    return [[m.sku, m.descripcion, m.piezas, m.largo, m.ancho, m.alto, m.peso,
             m.apilar, m.inclinar, m.rotar, m.max_camion, m.max_pallet]
            for m in s.scalars(select(Medida).order_by(Medida.sku)).all()]


def estado(s: Session) -> dict:
    from sqlalchemy import func
    total = s.scalar(select(func.count()).select_from(Medida)) or 0
    ultima = s.scalar(select(Medida.actualizado).order_by(Medida.actualizado.desc()).limit(1))
    return {"productos": total, "ultima_carga": ultima.isoformat(timespec="seconds") + "Z" if ultima else ""}
