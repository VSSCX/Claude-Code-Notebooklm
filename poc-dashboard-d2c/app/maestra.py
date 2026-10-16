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

from . import db, skus
from .config import settings
from .items import _n

CAND = {"sku": ["codigosap", "codsap", "sku", "material", "codigo", "codigoproducto", "matnr", "referencecode"],
        "clasif2": ["clasif2", "clasificacion2", "clasif02", "clasificacion02", "clasifdos", "clase2"],
        "producto": ["descripcion", "producto", "nombre", "nombreproducto", "denominacion", "descripcionmaterial", "maktx", "skuname"]}
TTL = 6 * 3600                     # la maestra casi no cambia: se vuelve a leer cada 6 horas
_LOCK = threading.Lock()
_CACHE: dict = {"t": 0.0, "df": None, "error": None, "falla": None}      # falla = (cuando, mensaje, tablas): no se reintenta por 5 minutos
ESPERA_FALLA = 300


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
    if rol == "clasif2":     # Clasif2, ClasificacionPrd2, DescClasif2...: se prefiere la que trae el nombre y no el codigo
        hay = [(n, c) for n, c in cols.items() if re.search(r"clasif\w*?0?2(?!\d)", n)]
        hay.sort(key=lambda x: not re.search(r"desc|nombre|nom", x[0]))
        return hay[0][1] if hay else None
    if rol == "producto":
        return next((cols[c] for c in CAND[rol] if c in cols and "clasif" not in c), None)
    return next((cols[c] for c in CAND[rol] if c in cols), None)


def _leer(sql: str) -> pd.DataFrame:
    return db.leer_vtex(sql) if settings.maestra_origen == "vtex" else db.leer_sap(sql)


def candidatas() -> list[str]:
    """Tablas del servidor cuyo nombre sugiere una maestra de productos, las mas probables primero."""
    try:
        t = _leer("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%maestr%' "
                  "OR TABLE_NAME LIKE '%producto%' OR TABLE_NAME LIKE '%material%' OR TABLE_NAME LIKE '%clasif%'")
    except Exception:  # noqa: BLE001
        return []
    nombres = [f"{a}.{b}" for a, b in zip(t["TABLE_SCHEMA"], t["TABLE_NAME"])]

    def prioridad(n: str):
        m = n.lower()
        malo = any(x in m for x in ("temp", "tmp", "histor", "forecast", "almacen", "tienda", "exclusiv"))
        return (malo, not ("maestr" in m and "producto" in m), "vtex" in m, "dim_producto" not in m and "maestr" not in m, m)
    return sorted(nombres, key=prioridad)


def _mapear(raw: pd.DataFrame):
    return (_col(raw, "sku", settings.maestra_col_sku), _col(raw, "clasif2", settings.maestra_col_clasif2),
            _col(raw, "producto", settings.maestra_col_producto))


def _detectar() -> tuple[str | None, pd.DataFrame | None, str]:
    """Prueba las tablas candidatas y se queda con la primera que trae codigo SAP y Clasif2. -> (tabla, datos, detalle de lo probado)."""
    probadas = []
    for nombre in candidatas()[:14]:
        try:
            raw = _leer(f"SELECT * FROM {_ident(nombre)}")
        except Exception:  # noqa: BLE001
            continue
        c_sku, c_cl, _ = _mapear(raw)
        if c_sku and c_cl:
            return nombre, raw, ""
        probadas.append(f"{nombre} ({', '.join(map(str, raw.columns[:12]))})")
    return None, None, "; ".join(probadas[:5])


def cargar() -> tuple[pd.DataFrame | None, str | None, list[str]]:
    """-> (maestra con SKU, Clasif2 y Producto, mensaje de error, tablas candidatas)."""
    if settings.demo:
        from .demo import maestra_demo
        return maestra_demo(), None, []
    if settings.fuente_snapshot:
        from . import snapshot
        try:
            m = snapshot.tabla("maestra")
        except Exception as e:  # noqa: BLE001
            return None, str(e)[:200], []
        if m is None or m.empty:
            return None, "El paquete de datos publicado no trae la maestra de productos.", []
        return m, None, []
    with _LOCK:
        if _CACHE["df"] is not None and time.time() - _CACHE["t"] < TTL:
            return _CACHE["df"], None, []
        if _CACHE["falla"] and time.time() - _CACHE["falla"][0] < ESPERA_FALLA:
            return None, _CACHE["falla"][1], _CACHE["falla"][2]
        res = _cargar_real()
        _CACHE["falla"] = (time.time(), res[1], res[2]) if res[0] is None else None
        return res


def _cargar_real() -> tuple[pd.DataFrame | None, str | None, list[str]]:
    tabla, raw = settings.maestra_tabla, None
    try:
        if tabla:
            raw = _leer(f"SELECT * FROM {_ident(tabla)}")
        else:                                          # sin MAESTRA_TABLA: se busca sola entre las tablas parecidas
            tabla, raw, probadas = _detectar()
            if raw is None:
                return None, ("No encontré sola la maestra de productos (una tabla con código SAP y Clasif2). Indica su nombre en el .env "
                              "(MAESTRA_TABLA)." + (f" Probé: {probadas}." if probadas else "")), candidatas()
    except Exception as e:  # noqa: BLE001
        return None, f"No pude leer la maestra {tabla or ''}: {str(e)[:200]}", candidatas()
    c_sku, c_cl, c_pr = _mapear(raw)
    if not c_sku or not c_cl:
        faltan = [n for n, c in (("código SAP", c_sku), ("Clasif2", c_cl)) if not c]
        return None, (f"En {tabla} no encontré la columna de {' ni de '.join(faltan)}. Indícalas en el .env "
                      f"(MAESTRA_COL_SKU, MAESTRA_COL_CLASIF2). Columnas disponibles: {', '.join(map(str, raw.columns))}."), []
    df = pd.DataFrame({"SKU": skus.limpiar(raw[c_sku]),
                       "Clasif2": raw[c_cl].astype(str).str.strip().replace({"": "Sin clasificar", "None": "Sin clasificar", "nan": "Sin clasificar"}),
                       "Producto": raw[c_pr].astype(str).str.strip() if c_pr else ""}).drop_duplicates("SKU")
    df.attrs["tabla"] = tabla
    _CACHE.update(t=time.time(), df=df)
    return df, None, []
