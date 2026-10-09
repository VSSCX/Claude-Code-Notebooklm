"""Ventas por clasificacion 2 de la maestra de productos, y por producto dentro de una clasificacion (el "zoom").

La venta es el monto de cada pedido (sin cancelados), repartido entre las clasificaciones de sus lineas; y respetan los mismos filtros
que el resto del tablero. Se piden aparte de /api/dashboard porque leer las lineas puede tardar la primera vez.
"""
from __future__ import annotations

import threading

import pandas as pd

from . import maestra, servicio
from .exportar import a_csv

_LOCK = threading.Lock()
_CACHE: dict = {"version": None, "items": {}}      # resultados ya calculados por filtros, validos mientras no cambien los datos
SIN_CLASIFICAR = "Sin clasificar"
SIN_LINEAS = "Sin detalle de líneas"


def _base(filtros: dict):
    """-> (una fila por linea con la venta que le toca, mensaje de error, tablas candidatas).

    La venta es el MONTO DEL PEDIDO (el mismo que suma el resto del tablero). Un pedido con lineas de varias clasificaciones se reparte
    en proporcion al valor de cada linea (o a sus unidades si no hay precio), asi la suma por clasificacion siempre es el monto de los pedidos."""
    dim, _hoy, lin, _info = servicio.lineas_todas()
    mae, err, cand = maestra.cargar()
    if mae is None:
        return None, err, cand
    pedidos = servicio.filtrar_pedidos(filtros)
    pedidos = pedidos[pedidos["Status"] != "canceled"][["Sequence", "Total_Value"]]
    return repartir(lin, pedidos, mae), None, []


def repartir(lin: pd.DataFrame, pedidos: pd.DataFrame, mae: pd.DataFrame) -> pd.DataFrame:
    """Una fila por linea con su Clasif2, Producto y la venta (monto del pedido repartido). Lo usan el grafico y el asistente."""
    m = lin.merge(pedidos, on="Sequence", how="inner").merge(mae, on="SKU", how="left")
    m["Clasif2"] = m["Clasif2"].fillna(SIN_CLASIFICAR)
    prod = m["Producto"].where(m["Producto"].fillna("").astype(bool), m["Descripcion"])
    m["Producto"] = prod.where(prod.fillna("").astype(bool), m["SKU"])
    peso = pd.to_numeric(m["Monto"], errors="coerce").fillna(0.0)
    peso = peso.where(peso.groupby(m["Sequence"]).transform("sum") > 0, m["Qty"].astype(float))     # sin precio: se reparte por unidades
    tot = peso.groupby(m["Sequence"]).transform("sum").replace(0, pd.NA)
    m["Venta"] = (m["Total_Value"].astype(float) * peso / tot).fillna(0.0)
    sin = pedidos[~pedidos["Sequence"].isin(m["Sequence"])]                                          # pedidos sin lineas: su monto no se pierde
    if len(sin):
        m = pd.concat([m, pd.DataFrame({"Sequence": sin["Sequence"], "Qty": 0.0, "SKU": "", "Clasif2": SIN_LINEAS,
                                        "Producto": "Pedidos sin detalle de líneas", "Venta": sin["Total_Value"].astype(float)})], ignore_index=True)
    m.attrs["maestra"] = mae.attrs.get("tabla")
    return m


def ventas(filtros: dict, clasif: str | None = None) -> dict:
    """Ventas por clasificacion 2 y, si se pide una, los productos de esa clasificacion."""
    filtros = {k: v for k, v in (filtros or {}).items() if k not in ("clasif2", "zoom_clasif", "orden_det", "orden_crit")}      # la propia seleccion no filtra su grafico
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
    g = m.groupby("Clasif2").agg(venta=("Venta", "sum"), unidades=("Qty", "sum"), pedidos=("Sequence", "nunique")).reset_index()
    g = g.sort_values("venta", ascending=False)
    res = {"ok": True, "total": float(m["Venta"].sum()), "unidades": float(m["Qty"].sum()),
           "clasif": [{"nombre": r.Clasif2, "venta": float(r.venta), "unidades": float(r.unidades), "pedidos": int(r.pedidos)} for r in g.itertuples()],
           "sin_clasificar": float(m.loc[m["Clasif2"] == SIN_CLASIFICAR, "Venta"].sum()), "productos": None, "clasif_sel": clasif, "fuente": m.attrs.get("maestra")}
    if clasif:
        p = m[m["Clasif2"] == clasif].groupby(["SKU", "Producto"]).agg(venta=("Venta", "sum"), unidades=("Qty", "sum")).reset_index()
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
    filtros = {k: v for k, v in (filtros or {}).items() if k not in ("clasif2", "zoom_clasif", "orden_det", "orden_crit")}
    m, err, _ = _base(filtros)
    if m is None:
        raise ValueError(err)
    if clasif:
        m = m[m["Clasif2"] == clasif]
    t = m.groupby(["Clasif2", "Producto"])["Venta"].sum().reset_index().sort_values(["Clasif2", "Venta"], ascending=[True, False])
    return a_csv(["Clasif2", "Producto", "Venta"], [(r.Clasif2, r.Producto, f"{r.Venta:.0f}") for r in t.itertuples()])
