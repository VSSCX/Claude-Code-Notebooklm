"""Maestra de productos: clasificacion 2 (Clasif2) y nombre del producto por codigo SAP.

No se conoce el nombre de la tabla ni de sus columnas en la base real: se indican en el .env (MAESTRA_TABLA, y si hace falta
MAESTRA_COL_SKU, MAESTRA_COL_CLASIF2, MAESTRA_COL_PRODUCTO). Si falta algo, `cargar` lo explica con las columnas disponibles
y `candidatas` lista las tablas del servidor que se parecen a una maestra, en vez de adivinar.
"""
from __future__ import annotations

import re
import threading
import time

import pandas as pd

from . import db
from .config import settings
from .items import _n

CAND = {"sku": ["codigosap", "codsap", "sku", "material", "codigo", "codigoproducto", "matnr", "referencecode"],
        "clasif2": ["clasif2", "clasificacion2", "clasif02", "clasificacion02", "clasifdos", "clase2"],
        "producto": ["descripcion", "producto", "nombre", "nombreproducto", "denominacion", "descripcionmaterial", "maktx", "skuname"]}
TTL = 6 * 3600                     # la maestra casi no cambia: se vuelve a leer cada 6 horas
_LOCK = threading.Lock()
_CACHE: dict = {"t": 0.0, "df": None, "error": None}


def _ident(nombre: str) -> str:
    """db.schema.tabla -> [db].[schema].[tabla], solo con letras, numeros y guion bajo (el nombre viene del .env)."""
    partes = nombre.split(".")
    if not 1 <= len(partes) <= 3 or not all(re.fullmatch(r"[A-Za-z0-9_]+", p) for p in partes):
        raise ValueError("MAESTRA_TABLA solo admite letras, numeros y guion bajo (por ejemplo dbo.maestra_productos)")
    return ".".join(f"[{p}]" for p in partes)


def _col(df: pd.DataFrame, rol: str, forzada: str):
    cols = {_n(c): c for c in df.columns}
    if forzada and _n(forzada) in cols:
        return cols[_n(forzada)]
    return next((cols[c] for c in CAND[rol] if c in cols), None)


def _leer(sql: str) -> pd.DataFrame:
    return db.leer_vtex(sql) if settings.maestra_origen == "vtex" else db.leer_sap(sql)


def candidatas() -> list[str]:
    """Tablas del servidor cuyo nombre sugiere una maestra de productos (ayuda para completar el .env)."""
    try:
        t = _leer("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%maestr%' "
                  "OR TABLE_NAME LIKE '%producto%' OR TABLE_NAME LIKE '%material%' OR TABLE_NAME LIKE '%clasif%'")
        return [f"{a}.{b}" for a, b in zip(t["TABLE_SCHEMA"], t["TABLE_NAME"])][:25]
    except Exception:  # noqa: BLE001
        return []


def cargar() -> tuple[pd.DataFrame | None, str | None, list[str]]:
    """-> (maestra con SKU, Clasif2 y Producto, mensaje de error, tablas candidatas)."""
    if settings.demo:
        from .demo import maestra_demo
        return maestra_demo(), None, []
    with _LOCK:
        if _CACHE["df"] is not None and time.time() - _CACHE["t"] < TTL:
            return _CACHE["df"], None, []
        if not settings.maestra_tabla:
            return None, ("Falta indicar la maestra de productos: define MAESTRA_TABLA en el .env (por ejemplo dbo.maestra_productos) "
                          "y, si no está en el ODS, MAESTRA_ORIGEN=vtex."), candidatas()
        try:
            raw = _leer(f"SELECT * FROM {_ident(settings.maestra_tabla)}")
        except Exception as e:  # noqa: BLE001
            return None, f"No pude leer la maestra {settings.maestra_tabla}: {str(e)[:200]}", candidatas()
        c_sku, c_cl = _col(raw, "sku", settings.maestra_col_sku), _col(raw, "clasif2", settings.maestra_col_clasif2)
        c_pr = _col(raw, "producto", settings.maestra_col_producto)
        if not c_sku or not c_cl:
            faltan = [n for n, c in (("código SAP", c_sku), ("Clasif2", c_cl)) if not c]
            return None, (f"En {settings.maestra_tabla} no encontré la columna de {' ni de '.join(faltan)}. Indícalas en el .env "
                          f"(MAESTRA_COL_SKU, MAESTRA_COL_CLASIF2). Columnas disponibles: {', '.join(map(str, raw.columns))}."), []
        df = pd.DataFrame({"SKU": raw[c_sku].astype(str).str.strip(),
                           "Clasif2": raw[c_cl].astype(str).str.strip().replace({"": "Sin clasificar", "None": "Sin clasificar", "nan": "Sin clasificar"}),
                           "Producto": raw[c_pr].astype(str).str.strip() if c_pr else ""}).drop_duplicates("SKU")
        _CACHE.update(t=time.time(), df=df)
        return df, None, []
