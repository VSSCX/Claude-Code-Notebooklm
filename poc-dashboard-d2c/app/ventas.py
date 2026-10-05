"""Ventas por clasificacion 2 de la maestra de productos, y por producto dentro de una clasificacion (el "zoom").

Las ventas salen de las lineas de los pedidos (cantidad x precio, sin pedidos cancelados) y respetan los mismos filtros
que el resto del tablero. Se piden aparte de /api/dashboard porque leer las lineas puede tardar la primera vez.
"""
from __future__ import annotations

import threading

import pandas as pd

from . import maestra, servicio

_LOCK = threading.Lock()
_CACHE: dict = {"version": None, "items": {}}      # resultados ya calculados por filtros, validos mientras no cambien los datos
SIN_CLASIFICAR = "Sin clasificar"


def _base(filtros: dict):
    """-> (lineas de las ventas con Clasif2 y Producto, mensaje de error, tablas candidatas)."""
    dim, _hoy, lin, info = servicio.lineas_todas()
    mae, err, cand = maestra.cargar()
    if mae is None:
        return None, err, cand
    if not info["mapa"]["precio_unitario"] and not info["mapa"]["monto"]:
        return None, ("No encontré la columna de precio en OrderItems, así que no puedo calcular ventas. Indica su nombre en el .env "
                      "(ITEM_COL_PRECIO). Columnas disponibles: " + ", ".join(info["columnas"]) + "."), []
    pedidos = servicio.filtrar_pedidos(filtros)
    pedidos = pedidos[pedidos["Status"] != "canceled"]
    m = lin.merge(pedidos[["Sequence"]], on="Sequence", how="inner").merge(mae, on="SKU", how="left")
    m["Clasif2"] = m["Clasif2"].fillna(SIN_CLASIFICAR)
    prod = m["Producto"].where(m["Producto"].fillna("").astype(bool), m["Descripcion"])
    m["Producto"] = prod.where(prod.fillna("").astype(bool), m["SKU"])
    m["Monto"] = m["Monto"].fillna(0.0)
    return m, None, []


def ventas(filtros: dict, clasif: str | None = None) -> dict:
    """Ventas por clasificacion 2 y, si se pide una, los productos de esa clasificacion."""
    filtros = {k: v for k, v in (filtros or {}).items() if k not in ("clasif2", "orden_det", "orden_crit")}
    llave = repr(sorted(filtros.items(), key=lambda kv: kv[0])) + "|" + str(clasif)
    version = servicio.version()
    with _LOCK:
        if _CACHE["version"] != version:
            _CACHE.update(version=version, items={})
        if llave in _CACHE["items"]:
            return _CACHE["items"][llave]
    m, err, cand = _base(filtros)
    if m is None:
        return {"ok": False, "motivo": err, "tablas": cand}
    g = m.groupby("Clasif2").agg(venta=("Monto", "sum"), unidades=("Qty", "sum"), pedidos=("Sequence", "nunique")).reset_index()
    g = g.sort_values("venta", ascending=False)
    res = {"ok": True, "total": float(m["Monto"].sum()), "unidades": float(m["Qty"].sum()),
           "clasif": [{"nombre": r.Clasif2, "venta": float(r.venta), "unidades": float(r.unidades), "pedidos": int(r.pedidos)} for r in g.itertuples()],
           "sin_clasificar": float(m.loc[m["Clasif2"] == SIN_CLASIFICAR, "Monto"].sum()), "productos": None, "clasif_sel": clasif}
    if clasif:
        p = m[m["Clasif2"] == clasif].groupby(["SKU", "Producto"]).agg(venta=("Monto", "sum"), unidades=("Qty", "sum")).reset_index()
        p = p.sort_values("venta", ascending=False)
        res["productos"] = [{"sku": r.SKU, "producto": r.Producto, "venta": float(r.venta), "unidades": float(r.unidades)} for r in p.head(200).itertuples()]
        res["n_productos"] = int(len(p))
    with _LOCK:
        if len(_CACHE["items"]) > 64:
            _CACHE["items"].clear()
        _CACHE["items"][llave] = res
    return res


def exportar_csv(filtros: dict, clasif: str | None = None) -> str:
    """CSV (punto y coma, UTF-8 con BOM: abre bien en Excel en espanol) con Clasif2 | Producto | Venta; una sola clasificacion o todas."""
    filtros = {k: v for k, v in (filtros or {}).items() if k not in ("clasif2", "orden_det", "orden_crit")}
    m, err, _ = _base(filtros)
    if m is None:
        raise ValueError(err)
    if clasif:
        m = m[m["Clasif2"] == clasif]
    t = m.groupby(["Clasif2", "Producto"])["Monto"].sum().reset_index().sort_values(["Clasif2", "Monto"], ascending=[True, False])
    c = lambda v: ('"' + str(v).replace('"', '""') + '"') if any(x in str(v) for x in ';"\n') else str(v)  # noqa: E731
    filas = ["Clasif2;Producto;Venta"] + [f"{c(r.Clasif2)};{c(r.Producto)};{r.Monto:.0f}" for r in t.itertuples()]
    return "\ufeff" + "\r\n".join(filas) + "\r\n"
