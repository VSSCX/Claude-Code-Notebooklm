"""Lineas de los pedidos (OrderItems): detalle de un pedido y base para el asistente de consultas.

No se conocen los nombres exactos de las columnas de descripcion y precio de OrderItems en la base real, asi que
se buscan por nombre (SKU_Name, Name, Selling_Price, Price...) y se pueden fijar en el .env (ITEM_COL_*).
VTEX suele guardar los precios en centavos: se detecta comparando la suma de las lineas con el Total_Value
del pedido (o se fuerza con ITEM_PRECIO_CENTAVOS=1 / 0). Todo lo que no se pueda inferir se informa en pantalla
junto con las columnas disponibles, en vez de inventarlo.
"""
from __future__ import annotations

import re
import threading

import pandas as pd

from . import queries
from .config import settings

CAND = {
    "desc": ["skuname", "productname", "itemname", "name", "description", "descripcion", "nombre", "skudescription", "refname"],
    "precio": ["sellingprice", "unitprice", "priceperunit", "itemprice", "price", "precio", "preciounitario", "skuprice"],
    "monto": ["totalprice", "linetotal", "linetotalprice", "amount", "monto", "subtotal", "total"],
    "sku": ["referencecode", "referenceid", "refid", "codigosap", "sapcode", "sku"],
    "qty": ["quantitysku", "quantity", "qty", "cantidad"],
}
_LOCK = threading.Lock()
_BULK: dict = {"version": None, "df": None, "info": None}


def _n(c) -> str:
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


def _col(df: pd.DataFrame, rol: str, forzada: str) -> str | None:
    cols = {_n(c): c for c in df.columns}
    if forzada and _n(forzada) in cols:
        return cols[_n(forzada)]
    for cand in CAND[rol]:
        if cand in cols:
            return cols[cand]
    return None


def normalizar(raw: pd.DataFrame, totales: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """Devuelve (lineas normalizadas, info). Columnas: Sequence, SKU, Descripcion, Qty, PrecioUnit, Monto."""
    st = settings
    c_seq = next((c for c in raw.columns if _n(c) == "sequence"), None)
    c_sku, c_desc = _col(raw, "sku", st.item_col_sku), _col(raw, "desc", st.item_col_desc)
    c_qty, c_pre = _col(raw, "qty", ""), _col(raw, "precio", st.item_col_precio)
    c_mon = _col(raw, "monto", st.item_col_monto)
    info = {"columnas": [str(c) for c in raw.columns], "mapa": {"sku": c_sku, "descripcion": c_desc, "cantidad": c_qty,
            "precio_unitario": c_pre, "monto": c_mon}, "centavos": False}
    if raw.empty or c_seq is None:
        return pd.DataFrame(columns=["Sequence", "SKU", "Descripcion", "Qty", "PrecioUnit", "Monto"]), info
    out = pd.DataFrame({"Sequence": raw[c_seq].astype(str).str.strip()})
    out["SKU"] = raw[c_sku].astype(str).str.strip() if c_sku else ""
    out["Descripcion"] = raw[c_desc].astype(str).str.strip() if c_desc else ""
    out["Qty"] = pd.to_numeric(raw[c_qty], errors="coerce").fillna(0) if c_qty else 0
    pre = pd.to_numeric(raw[c_pre], errors="coerce") if c_pre else None
    mon = pd.to_numeric(raw[c_mon], errors="coerce") if c_mon else None
    if pre is None and mon is not None:
        pre = mon / out["Qty"].where(out["Qty"] > 0)
    if mon is None and pre is not None:
        mon = pre * out["Qty"]
    # centavos: se compara el total de las lineas con el Total_Value del pedido
    cent = {"1": True, "0": False}.get(st.item_precio_centavos)
    if cent is None:
        cent = False
        if mon is not None and totales is not None:
            suma = mon.groupby(out["Sequence"]).sum()
            r = (suma / totales.reindex(suma.index).replace(0, pd.NA)).dropna().astype(float)
            cent = bool(len(r)) and float(r.median()) > 20
    info["centavos"] = cent
    f = 100.0 if cent else 1.0
    out["PrecioUnit"] = None if pre is None else pre / f
    out["Monto"] = None if mon is None else mon / f
    return out, info


def _totales(dim: pd.DataFrame) -> pd.Series:
    return dim.drop_duplicates("Sequence").set_index("Sequence")["Total_Value"].astype(float)


def lineas_pedido(sequence: str, dim: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Lineas de un pedido. En demo salen de la carga de ejemplo; en real, de OrderItems (consulta parametrizada)."""
    if settings.demo:
        from .demo import lineas_demo
        raw = lineas_demo()
        raw = raw[raw["Sequence"].astype(str) == str(sequence)] if len(raw) else raw
    else:
        raw = queries.q_items_pedido(sequence)
    tot = _totales(dim[dim["Sequence"] == str(sequence)])
    return normalizar(raw, tot)


def todas(version: str, dim: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Todas las lineas, para el asistente. En modo real la primera vez tarda (carga completa, solo al usar el asistente);
    despues, cuando llegan pedidos nuevos, se piden solo las lineas de esos pedidos en vez de recargar todo."""
    with _LOCK:
        if _BULK["version"] == version and _BULK["df"] is not None:
            return _BULK["df"], _BULK["info"]
        if settings.demo:
            from .demo import lineas_demo
            df, info = normalizar(lineas_demo(), _totales(dim))
        elif _BULK["df"] is None:
            df, info = normalizar(queries.q_items_todos(), _totales(dim))
        else:
            faltan = sorted(set(dim["Sequence"].astype(str)) - set(_BULK["df"]["Sequence"]))
            if not faltan:
                df, info = _BULK["df"], _BULK["info"]
            elif len(faltan) > 3000:
                df, info = normalizar(queries.q_items_todos(), _totales(dim))
            else:
                nuevas, _ = normalizar(queries.q_items_por_secuencias(faltan), _totales(dim))
                df, info = pd.concat([_BULK["df"], nuevas], ignore_index=True), _BULK["info"]
        _BULK.update(version=version, df=df, info=info)
        return df, info
