"""Orquesta la carga de datos y arma los agregados de cada pagina del dashboard.

ACTUALIZACION EN VIVO
  - Un monitor en segundo plano hace cada pocos segundos una consulta LIVIANA (solo conteos).
  - Si detecta un cambio (pedido nuevo, cambio de estado, ingreso a SAP, factura) recarga TODO
    al tiro. Si no hay cambios, no molesta a las bases.
  - El navegador pregunta cada pocos segundos por la "version" (consulta barata, sin SQL).

Los filtros (slicers, marcadores) se aplican en memoria: responden al instante.
"""
from __future__ import annotations

import hashlib
import math
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from . import items as lineas, modelo, queries
from .config import settings
from .demo import datos_demo, firma_demo

_RELOAD_LOCK = threading.Lock()
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_CACHE: dict = {"ts": 0.0, "dim": None, "hoy": None, "ref": None, "version": "0",
                "error": None, "consulta": None, "ultimo_pedido": None}
_MON: dict = {"firma": None, "ultima_ok": 0.0, "error": None, "cargas": 0}
_PROG: dict = {"inicio": None, "pasos": {}, "total": None, "modelo": None}   # avance y tiempos de la carga
_PRIMERA_VEZ: dict = {}        # Sequence -> instante en que se vio por primera vez (tras la 1a carga)

ORDEN_ESTADO = ["Integrado · Pendiente", "No integrado · Pendiente",
                "No integrado · Facturado", "Integrado · Facturado", "Cancelado"]
ABIERTOS = ["Integrado · Pendiente", "No integrado · Pendiente", "No integrado · Facturado"]
COLOR_ESTADO = {
    "Integrado · Facturado": "#2F9E6B", "Integrado · Pendiente": "#3B7DD8",
    "No integrado · Facturado": "#D0483A", "No integrado · Pendiente": "#E09A22",
    "Cancelado": "#A3AFBD",
}
BASE_BODEGA = ["EC01", "POST_Fechado"]
# Marcadores del Power BI: cada boton fija su propio alcance (igual que los bookmarks).
ALERTAS = {
    "bws": {"col": "Alerta BWS", "val": "Atención BWS", "ov": {"bodega": ["EC01"], "sla_excluir": ["Servicios"]}},
    "pos": {"col": "Alerta POST Fechado", "val": "POST Fechado", "ov": {"bodega": BASE_BODEGA}},
    "mkp": {"col": "Alerta MKP", "val": "Atención MKP", "ov": {"bodega": BASE_BODEGA}},
    "fac": {"col": "Facturado Sin Despacho", "val": "Facturado sin despacho", "ov": {"bodega": BASE_BODEGA}},
}
DIM_KEYS = ("canal", "cliente", "status", "sla", "sla_excluir", "bodega", "buscar")


# --------------------------------------------------------------------------- utilidades
def _sanear(obj):
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanear(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanear(v) for v in obj]
    if isinstance(obj, np.floating):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    try:
        if obj is pd.NaT or pd.isna(obj):
            return None
    except (ValueError, TypeError):
        pass
    return obj


def _cargar_crudo():
    """Ejecuta las 6 consultas EN PARALELO (VTEX y SAP estan en servidores distintos) y mide cada una."""
    if settings.demo:
        t0 = time.time()
        r = datos_demo()
        _PROG.update(inicio=t0, total=round(time.time() - t0, 1),
                     pasos={"Datos de ejemplo": {"estado": "ok", "seg": round(time.time() - t0, 1), "filas": len(r[0])}})
        return r
    tareas = {"Pedidos VTEX": queries.q_orders, "Líneas VTEX": queries.q_order_items,
              "Ingresos SAP": queries.q_sap_ingresos, "Facturación SAP": queries.q_facturacion,
              "Stock VTEX": queries.q_stock_vtex, "Fecha de hoy": queries.q_hoy_cl}
    _PROG.update(inicio=time.time(), total=None, pasos={k: {"estado": "cargando"} for k in tareas})

    def correr(nombre, fn):
        t0 = time.time()
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001
            _PROG["pasos"][nombre] = {"estado": "error", "seg": round(time.time() - t0, 1)}
            raise RuntimeError(f"{nombre}: {e}") from e
        filas = len(r) if isinstance(r, pd.DataFrame) else None
        _PROG["pasos"][nombre] = {"estado": "ok", "seg": round(time.time() - t0, 1), "filas": filas}
        print(f"  [carga] {nombre}: {time.time() - t0:.1f} s" + (f", {filas} filas" if filas is not None else ""), flush=True)
        return r

    with ThreadPoolExecutor(max_workers=len(tareas)) as ex:
        fut = {k: ex.submit(correr, k, fn) for k, fn in tareas.items()}
        res = {k: f.result() for k, f in fut.items()}
    _PROG["total"] = round(time.time() - _PROG["inicio"], 1)
    print(f"  [carga] consultas listas en {_PROG['total']} s (en paralelo)", flush=True)
    return (res["Pedidos VTEX"], res["Líneas VTEX"], res["Ingresos SAP"],
            res["Facturación SAP"], res["Stock VTEX"], res["Fecha de hoy"])


# --------------------------------------------------------------------------- carga y monitor
def _recargar(forzar: bool = False):
    """Carga completa de las bases y reconstruccion del modelo. Una a la vez."""
    with _RELOAD_LOCK:
        if not forzar and _CACHE["dim"] is not None:
            return
        orders, items, sap, fact, stock, hoy = _cargar_crudo()
        tm = time.time()
        m = modelo.construir(orders, items, sap, fact, stock, hoy)
        _PROG["modelo"] = round(time.time() - tm, 1)
        dim, hoy, ref = m["dim"], m["hoy"], m["ref"]
        ultimo = None
        try:
            col = "Creation_DateTime" if "Creation_DateTime" in orders.columns else "Creation_Date"
            u = pd.to_datetime(orders[col]).max()
            ultimo = None if pd.isna(u) else u.strftime("%d-%m-%y %H:%M")
        except Exception:  # noqa: BLE001
            pass
        h = int(pd.util.hash_pandas_object(
            dim[["Sequence", "Status", "Estado Ingreso", "Facturado Sin Despacho"]].astype(str),
            index=False).sum())
        ver = hashlib.md5(f"{len(dim)}|{h}|{ref}".encode()).hexdigest()[:12]
        ahora = time.time()
        prev = _CACHE["dim"]
        if prev is not None:                       # pedidos que no estaban en la carga anterior
            for s in set(dim["Sequence"]) - set(prev["Sequence"]):
                _PRIMERA_VEZ.setdefault(s, ahora)
        for s in [s for s, t in _PRIMERA_VEZ.items() if ahora - t > 3600]:
            _PRIMERA_VEZ.pop(s, None)
        _CACHE.update(ts=ahora, dim=dim, hoy=hoy, ref=ref, version=ver, error=None, stock=stock,
                      consulta=time.strftime("%H:%M:%S"), ultimo_pedido=ultimo)
        _MON["cargas"] += 1


def _cargar_dim():
    if _CACHE["dim"] is None:
        try:
            _recargar()
        except Exception as e:  # noqa: BLE001
            _CACHE["error"] = {"msg": str(e), "trace": traceback.format_exc()[-1500:]}
            raise
    elif (_THREAD is None or not _THREAD.is_alive()) and time.time() - _CACHE["ts"] > settings.recarga_maxima:
        _recargar(forzar=True)         # sin monitor activo: igual se mantiene al dia
    return _CACHE["dim"], _CACHE["hoy"]


def _firma() -> str:
    return str(firma_demo()) if settings.demo else queries.q_firma()


def _monitor():
    while not _STOP.is_set():
        firma = None
        try:                                     # 1) deteccion rapida de cambios (consulta liviana)
            firma = _firma()
            _MON.update(ultima_ok=time.time(), error=None)
        except Exception as e:  # noqa: BLE001
            _MON["error"] = str(e)[:220]
        try:                                     # 2) recarga completa si hubo cambio, o de respaldo cada
            vieja = time.time() - _CACHE["ts"] > settings.recarga_maxima   # RECARGA_MAXIMA aunque 1) falle
            cambio = firma is not None and firma != _MON["firma"]
            if _CACHE["dim"] is None or cambio or vieja:
                _recargar(forzar=True)
                if firma is not None:
                    _MON["firma"] = firma
        except Exception as e:  # noqa: BLE001
            _MON["error"] = str(e)[:220]
        _STOP.wait(settings.revisar_cada)


def iniciar_monitor():
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_monitor, name="monitor-cambios", daemon=True)
    _THREAD.start()


def detener_monitor():
    _STOP.set()


def estado_version() -> dict:
    """Respuesta barata para el navegador: version actual + hace cuanto se reviso por ultima vez."""
    ahora = time.time()
    rev = int(ahora - _MON["ultima_ok"]) if _MON["ultima_ok"] else None
    # 'lento': falla la deteccion rapida pero los datos se siguen recargando (respaldo)
    estado = "ok"
    if _MON["error"]:
        al_dia = _CACHE["dim"] is not None and ahora - _CACHE["ts"] <= settings.recarga_maxima + 3 * settings.revisar_cada
        estado = "lento" if al_dia else "sin_bases"
    return {"version": _CACHE["version"], "revisado": rev, "error": _MON["error"], "estado": estado,
            "respaldo_min": max(1, round(settings.recarga_maxima / 60)),
            "carga": {"inicio": _PROG["inicio"], "pasos": _PROG["pasos"], "total": _PROG["total"], "modelo": _PROG["modelo"]},
            "consulta": _CACHE["consulta"], "cargado": _CACHE["dim"] is not None,
            "poll": settings.navegador_cada}


def version() -> str:
    _cargar_dim()
    return _CACHE["version"]


def _snapshot():
    _cargar_dim()
    return _CACHE["dim"], _CACHE["hoy"], _CACHE["ref"]


# --------------------------------------------------------------------------- filtros
def opciones_filtros() -> dict:
    dim, hoy, ref = _snapshot()

    def ops(col):
        return sorted(str(x) for x in dim[col].dropna().unique())
    fechas = dim["Creation_Date"].dropna()
    return {"canal": ops("Canal"), "cliente": ops("SalesChannelName"), "status": ops("Status"),
            "sla": ops("SLA_Type"), "bodega": ops("warehouse"), "bodega_base": BASE_BODEGA,
            "estado_pedido": ORDEN_ESTADO, "hoy": hoy.strftime("%Y-%m-%d"),
            "fecha_min": fechas.min().strftime("%Y-%m-%d"), "fecha_max": fechas.max().strftime("%Y-%m-%d")}


def _sel_dia(f: dict) -> bool:
    """Un clic en una barra de dia deja desde = hasta: es una seleccion de dia (como en Power BI)."""
    return bool(f.get("fecha_ini") and f.get("fecha_fin") and f["fecha_ini"] == f["fecha_fin"])


def _sel_mes(f: dict) -> bool:
    """Un clic en una barra de mes deja del dia 1 a un dia del mismo mes."""
    ini, fin = str(f.get("fecha_ini") or ""), str(f.get("fecha_fin") or "")
    return len(ini) == 10 and len(fin) == 10 and ini[:7] == fin[:7] and ini[8:10] == "01"


def _aplicar_filtros(dim: pd.DataFrame, f: dict) -> pd.DataFrame:
    d = dim
    if f.get("alcance") == "abiertos":                       # = filtro de pagina Trazabilidad "En seguimiento"
        d = d[d["Trazabilidad"] == "En seguimiento"]
    if f.get("bodega"):
        d = d[d["warehouse"].isin(f["bodega"])]
    if f.get("sla_excluir"):
        d = d[~d["SLA_Type"].isin(f["sla_excluir"])]
    if f.get("canal"):
        d = d[d["Canal"].isin(f["canal"])]
    if f.get("cliente"):
        d = d[d["SalesChannelName"].isin(f["cliente"])]
    if f.get("status"):
        d = d[d["Status"].isin(f["status"])]
    if f.get("sla"):
        d = d[d["SLA_Type"].isin(f["sla"])]
    q = str(f.get("buscar") or "").strip()
    if q:
        m = (d["Sequence"].astype(str).str.contains(q, case=False, regex=False, na=False)
             | d["Order"].astype(str).str.contains(q, case=False, regex=False, na=False)
             | d["Pedido SAP"].astype(str).str.contains(q, case=False, regex=False, na=False))
        d = d[m]
    if f.get("fecha_ini"):
        d = d[d["Creation_Date"] >= pd.Timestamp(f["fecha_ini"])]
    if f.get("fecha_fin"):
        d = d[d["Creation_Date"] <= pd.Timestamp(f["fecha_fin"])]
    t = f.get("tarjeta")
    if t == "ing":
        d = d[d["Estado Ingreso"] == "Ingresado"]
    elif t == "noing":
        d = d[d["Estado Ingreso"] == "No ingresado"]
    elif t == "canc":
        d = d[d["Estado Ingreso"] == "Cancelado VTEX"]
    a = ALERTAS.get(f.get("alerta") or "")
    if a:
        d = d[d[a["col"]] == a["val"]]
    return d


# --------------------------------------------------------------------------- agregados
def _delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 4)


def _mtd_anterior(dim, hoy):
    """Mismo tramo (dia 1 al dia de hoy) del mes anterior."""
    dia = hoy.day
    fin_ant = hoy.replace(day=1) - pd.Timedelta(days=1)
    ini_ant = fin_ant.replace(day=1)
    corte = min(ini_ant + pd.Timedelta(days=dia - 1), fin_ant)
    sub = dim[(dim["Creation_Date"] >= ini_ant) & (dim["Creation_Date"] <= corte)]
    return modelo.medidas(sub) if len(sub) else {}


def _matriz(dim):
    """Pedidos por dia de CREACION x estado (pestana Diagnostico)."""
    if not len(dim):
        return {"fechas": [], "columnas": ORDEN_ESTADO, "filas": [],
                "totales_col": [0] * len(ORDEN_ESTADO), "totales_fila": [], "total": 0}
    piv = dim.pivot_table(index=dim["Creation_Date"].dt.strftime("%Y-%m-%d"), columns="Estado Pedido",
                          values="Sequence", aggfunc="count", fill_value=0)
    for c in ORDEN_ESTADO:
        if c not in piv.columns:
            piv[c] = 0
    piv = piv[ORDEN_ESTADO]
    return {"fechas": list(piv.index), "columnas": ORDEN_ESTADO, "filas": piv.values.tolist(),
            "totales_col": piv.sum(axis=0).tolist(), "totales_fila": piv.sum(axis=1).tolist(),
            "total": int(piv.values.sum())}


def _matriz_entrega(dim, hoy):
    """Pedidos ABIERTOS por dia de ENTREGA ESTIMADA x estado (la matriz de la pagina Pedidos del Power BI)."""
    d = dim[dim["Estado Pedido"].isin(ABIERTOS) & dim["Shipping_Estimate_Date"].notna()
            & (dim["Shipping_Estimate_Date"].dt.year >= 2000)]
    vacio = {"cols": [], "estados": ABIERTOS, "filas": [[] for _ in ABIERTOS], "totales": [], "total": 0}
    if not len(d):
        return vacio
    ini, fin = hoy - pd.Timedelta(days=6), hoy + pd.Timedelta(days=14)
    clave = d["Shipping_Estimate_Date"].map(
        lambda x: "<" if x < ini else (">" if x > fin else x.strftime("%Y-%m-%d")))
    piv = d.assign(_k=clave).pivot_table(index="Estado Pedido", columns="_k", values="Sequence",
                                         aggfunc="count", fill_value=0).reindex(ABIERTOS, fill_value=0)
    fechas = sorted(c for c in piv.columns if c not in ("<", ">"))
    orden = (["<"] if "<" in piv.columns else []) + fechas + ([">"] if ">" in piv.columns else [])
    cols = []
    for k in orden:
        if k == "<":
            cols.append({"k": k, "etq": "Anteriores", "rel": -1})
        elif k == ">":
            cols.append({"k": k, "etq": "Posteriores", "rel": 1})
        else:
            f = pd.Timestamp(k)
            cols.append({"k": k, "etq": f.strftime("%d-%m"), "rel": -1 if f < hoy else (0 if f == hoy else 1)})
    piv = piv[orden]
    return {"cols": cols, "estados": ABIERTOS, "filas": piv.values.tolist(),
            "totales": piv.sum(axis=0).tolist(), "total": int(piv.values.sum())}


def _cierre(base, hoy):
    """% cumplimiento y antiguedad promedio al CIERRE de cada mes ya terminado (medida 'Es Mes Cerrado')."""
    actual = hoy.strftime("%Y-%m")
    meses, cumpl, antig = [], [], []
    for mes, g in base.groupby("Mes"):
        if mes >= actual:
            continue
        b = g[g["Cumple Entrega al Cierre"].notna()]
        a = g["Antigüedad al Cierre"].dropna()
        meses.append(mes)
        cumpl.append(round(float((b["Cumple Entrega al Cierre"] == "En plazo").mean()), 4) if len(b) else None)
        antig.append(round(float(a.mean()), 2) if len(a) else None)
    return {"meses": meses, "cumpl": cumpl, "antig": antig}


def _composicion(dim):
    if not len(dim):
        return {"meses": [], "columnas": ORDEN_ESTADO, "filas": []}
    comp = dim.pivot_table(index="Mes", columns="Estado Pedido", values="Sequence", aggfunc="count", fill_value=0)
    for c in ORDEN_ESTADO:
        if c not in comp.columns:
            comp[c] = 0
    comp = comp[ORDEN_ESTADO].sort_index()
    return {"meses": list(comp.index), "columnas": ORDEN_ESTADO, "filas": comp.values.tolist()}


def _canal(dim, sin_fecha, hoy):
    """Riesgo por canal. 'Vigentes' = vigentes del MES ACTUAL (igual que 'Pedidos Vigentes Mes Actual')."""
    mes_ini = hoy.replace(day=1)
    mes = sin_fecha[(sin_fecha["Creation_Date"] >= mes_ini) & (sin_fecha["Creation_Date"] <= hoy)]
    vm = mes[mes["Estado Pedido"] != "Cancelado"].groupby("Canal").size()
    pm = mes[mes["Status"] == "ready-for-handling"].groupby("Canal").size()
    out = []
    for c in sorted(set(dim["Canal"].unique()) | set(vm.index)):
        g = dim[dim["Canal"] == c]
        v = int(vm.get(c, 0))
        pp = int(pm.get(c, 0))
        no_int = g.loc[g["Estado Ingreso"] == "No ingresado", "Total_Value"].sum()
        fsd = g.loc[g["Facturado Sin Despacho"] == "Facturado sin despacho", "Total_Value"].sum()
        out.append({"canal": c, "vigentes": v, "pendientes": pp,
                    "pct_pendiente": round(pp / v, 4) if v else None,
                    "monto_riesgo": float((no_int or 0) + (fsd or 0))})
    out.sort(key=lambda x: x["monto_riesgo"], reverse=True)
    return out


def _top(dim, col, n=12):
    vc = dim[col].value_counts().head(n)
    return {"labels": [str(x) for x in vc.index], "valores": [int(v) for v in vc.values],
            "total": int(dim[col].nunique())}


# Columnas por las que se puede ordenar cada tabla (clave del navegador -> columna del modelo)
ORDEN_DET = {"sequence": "Sequence", "pedido_sap": "Pedido SAP", "estado": "Estado Pedido", "canal": "Canal",
             "sla": "SLA_Type", "fecha": "Creation_Date", "sed": "Shipping_Estimate_Date", "monto": "Total_Value"}
ORDEN_CRIT = {"sequence": "Sequence", "canal": "Canal", "dias": "Dias Facturado Pendiente", "monto": "Total_Value"}


def _ordenar(df, orden, mapa):
    """Ordena TODO el conjunto filtrado (no solo lo visible). Vacios siempre al final.
    Empate (ej. misma fecha de creacion): Sequence, en el mismo sentido (mayor = mas reciente)."""
    if not isinstance(orden, dict) or orden.get("col") not in mapa:
        return None
    asc = orden.get("dir") != "desc"
    col = mapa[orden["col"]]
    d = df.copy()
    k = d[col]
    if col in ("Sequence", "Pedido SAP"):
        k = pd.to_numeric(k.replace("", np.nan), errors="coerce").fillna(
            pd.to_numeric(k.astype(str).str.extract(r"(\d+)")[0], errors="coerce"))
    d["_k"] = k
    d["_s"] = pd.to_numeric(d["Sequence"], errors="coerce")
    return d.sort_values(["_k", "_s"], ascending=[asc, asc], na_position="last", kind="mergesort")


def _criticos(dim, orden=None):
    crit = dim[dim["Facturado Sin Despacho"] == "Facturado sin despacho"].copy()
    o = _ordenar(crit, orden, ORDEN_CRIT)
    crit = o if o is not None else crit.sort_values("Dias Facturado Pendiente", ascending=False)
    filas = [{"sequence": r["Sequence"], "canal": r["Canal"],
              "dias": None if pd.isna(r["Dias Facturado Pendiente"]) else int(r["Dias Facturado Pendiente"]),
              "monto": float(r["Total_Value"] or 0), "pedido_sap": r["Pedido SAP"]}
             for _, r in crit.head(80).iterrows()]
    return filas, {"n": int(len(crit)), "monto": float(crit["Total_Value"].sum() or 0)}


COLS_DET = ["Sequence", "Creation_Date", "Estado Pedido", "Canal", "SLA_Type", "warehouse", "Status", "Total_Value",
            "Pedido SAP", "Shipping_Estimate_Date", "Antigüedad Días"]


def _fecha(serie):
    return serie.dt.strftime("%Y-%m-%d").fillna("").tolist()


def _detalle(dim, recientes, orden=None):
    det = dim[COLS_DET].copy()               # solo las columnas que se muestran: copiar las ~40 del modelo era lo mas caro
    det["_nuevo"] = det["Sequence"].isin(recientes)
    det["_ord"] = det["Estado Pedido"].map({e: i for i, e in enumerate(ORDEN_ESTADO)}).fillna(9)
    o = _ordenar(det, orden, ORDEN_DET)
    if o is not None:
        det = o.head(500)                    # orden elegido por el usuario sobre TODO el conjunto
    else:
        det = det.sort_values(["_nuevo", "_ord", "Antigüedad Días"], ascending=[False, True, False]).head(500)
    cols = zip(det["Sequence"], _fecha(det["Creation_Date"]), det["Estado Pedido"], det["Canal"], det["SLA_Type"],
               det["warehouse"], det["Status"], det["Total_Value"].fillna(0).astype(float), det["Pedido SAP"],
               det["_nuevo"], _fecha(det["Shipping_Estimate_Date"]))
    return [{"sequence": sq, "fecha": f, "estado": e, "canal": c, "sla": sla, "warehouse": w, "status": st, "monto": m,
             "pedido_sap": ps, "nuevo": bool(n), "sed": sed} for sq, f, e, c, sla, w, st, m, ps, n, sed in cols]


def construir(filtros: dict) -> dict:
    dim_full, hoy, ref = _snapshot()
    f = dict(filtros or {})
    dim = _aplicar_filtros(dim_full, f)
    dim.attrs["hoy"] = hoy
    sin_fecha = _aplicar_filtros(dim_full, {**f, "fecha_ini": None, "fecha_fin": None})
    # Filtrado cruzado como en Power BI: el grafico donde se hizo clic NO se filtra por su propia seleccion
    # (sigue mostrando todas las barras; el navegador resalta las elegidas). Los demas si se filtran.
    dim_sla = _aplicar_filtros(dim_full, {**f, "sla": None})
    dim_cli = _aplicar_filtros(dim_full, {**f, "cliente": None})
    dim_mes = sin_fecha if (_sel_mes(f) or _sel_dia(f)) else dim            # composicion: muestra todos los meses
    dim_dia = sin_fecha if _sel_dia(f) else dim                              # estado por dia: muestra todos los dias
    mes_ini = hoy.replace(day=1)
    mes = sin_fecha[(sin_fecha["Creation_Date"] >= mes_ini) & (sin_fecha["Creation_Date"] <= hoy)]
    vig_mes = int((mes["Estado Pedido"] != "Cancelado").sum())
    pp_mes = int((mes["Status"] == "ready-for-handling").sum())
    kpi = modelo.medidas(dim)
    kpi["pct_pendiente"] = round(pp_mes / vig_mes, 4) if vig_mes else None
    base = _aplicar_filtros(dim_full, {k: f.get(k) for k in DIM_KEYS})
    mtd = _mtd_anterior(base, hoy)

    def d(k):
        return _delta(kpi.get(k), mtd.get(k)) if mtd else None

    # tarjetas: cuentan todo el alcance (la seleccion de una tarjeta no apaga a las demas)
    dim_t = _aplicar_filtros(dim_full, {**f, "tarjeta": None})
    tarjetas = {"Órdenes VTEX": int(len(dim_t)),
                "Órdenes Integradas": int((dim_t["Estado Ingreso"] == "Ingresado").sum()),
                "Órdenes Sin PV": int((dim_t["Estado Ingreso"] == "No ingresado").sum()),
                "Órdenes Canceladas": int((dim_t["Estado Ingreso"] == "Cancelado VTEX").sum())}
    # botones de alerta: el numero es exactamente lo que se vera al presionarlos
    alertas = {}
    for k, cfg in ALERTAS.items():
        d2 = _aplicar_filtros(dim_full, {**f, "alerta": None, "tarjeta": None, "alcance": "todos", **cfg["ov"]})
        alertas[k] = int((d2[cfg["col"]] == cfg["val"]).sum())

    pend = dim[(dim["Status"] == "ready-for-handling") & (dim["Estado Ingreso"] == "Ingresado")]
    causa = pend["Causa Pendiente"].value_counts().to_dict() if len(pend) else {}

    ahora = time.time()
    recientes = {s for s, t in _PRIMERA_VEZ.items() if ahora - t <= settings.nuevo_segundos}
    llegadas = []
    if recientes:
        sub = dim_full[dim_full["Sequence"].isin(recientes)]
        for _, r in sub.iterrows():
            llegadas.append({"seq": r["Sequence"], "canal": r["Canal"], "estado": r["Estado Pedido"],
                             "hace": int(ahora - _PRIMERA_VEZ[r["Sequence"]])})
        llegadas.sort(key=lambda x: x["hace"])
        llegadas = llegadas[:30]

    crit_filas, crit_tot = _criticos(dim, f.get("orden_crit"))
    ejecutivo = {
        "pct_integracion": {"v": kpi["pct_integracion"], "d": d("pct_integracion"), "mejor": "arriba"},
        "pct_pendiente": {"v": kpi["pct_pendiente"], "d": d("pct_pendiente"), "mejor": "abajo"},
        "pct_cumplimiento": {"v": kpi["pct_cumplimiento"], "d": None, "mejor": "arriba"},
        "antig_prom": {"v": kpi["antig_prom"], "d": None, "mejor": "abajo"},
        "pct_fac_sd": {"v": kpi["pct_fac_sd"], "d": d("pct_fac_sd"), "mejor": "abajo"},
        "monto_en_riesgo": {"v": kpi["monto_en_riesgo"], "d": None, "mejor": "abajo"}}

    payload = {
        "hoy": hoy.strftime("%Y-%m-%d"), "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": _CACHE["version"], "consulta": _CACHE["consulta"], "ultimo_pedido": _CACHE["ultimo_pedido"],
        "kpi": kpi, "ejecutivo": ejecutivo, "tarjetas": tarjetas, "alertas": alertas, "causa": causa,
        "matriz_entrega": _matriz_entrega(dim, hoy), "matriz_dia": _matriz(dim_dia),
        "composicion": _composicion(dim_mes), "canal": _canal(dim, sin_fecha, hoy),
        "cierre": _cierre(base, hoy),
        "g_sla": _top(dim_sla, "SLA_Type"), "g_cli": _top(dim_cli, "SalesChannelName"),
        "g_noint": _top(dim_cli[dim_cli["Estado Ingreso"] == "No ingresado"], "SalesChannelName"),
        "tabla_criticos": crit_filas, "criticos_total": crit_tot,
        "detalle": _detalle(dim, recientes, f.get("orden_det")), "nuevos": [x["sequence"] for x in []],
        "llegadas": llegadas, "color_estado": COLOR_ESTADO, "orden_estado": ORDEN_ESTADO,
        "n_filtrado": int(len(dim)), "n_total": int(len(dim_full))}
    payload["nuevos"] = [r["sequence"] for r in payload["detalle"] if r["nuevo"]]
    if _CACHE.get("error"):
        payload["error"] = _CACHE["error"]["msg"]
    return _sanear(payload)


def detalle_pedido(sequence: str) -> dict | None:
    """Cabecera + lineas (codigo SAP, descripcion, cantidad, precio, monto) de un pedido, para el cajon de detalle."""
    dim, hoy, _ = _snapshot()
    sq = str(sequence).strip()
    fila = dim[dim["Sequence"] == sq]
    if fila.empty:
        return None
    r = fila.iloc[0]
    sed = r["Shipping_Estimate_Date"]
    cab = {"sequence": sq, "orden": r["Order"], "estado": r["Estado Pedido"], "status": r["Status"], "canal": r["Canal"],
           "cliente": r["SalesChannelName"], "sla": r["SLA_Type"], "warehouse": r["warehouse"],
           "fecha": r["Creation_Date"].strftime("%Y-%m-%d"), "sed": sed.strftime("%Y-%m-%d") if pd.notna(sed) else "",
           "pedido_sap": r["Pedido SAP"], "monto": float(r["Total_Value"] or 0), "unidades": float(r["Unidades"] or 0),
           "causa": r.get("Causa Pendiente") if r["Status"] == "ready-for-handling" and r["Estado Ingreso"] == "Ingresado" else None}
    out = {"pedido": cab, "lineas": [], "aviso": None, "columnas": []}
    try:
        df, info = lineas.lineas_pedido(sq, dim)
    except Exception as e:  # noqa: BLE001
        out["aviso"] = ("No se pudieron leer las líneas del pedido." if settings.serverless else
                        "No se pudieron leer las líneas del pedido: " + str(e)[:200])
        return _sanear(out)
    out["columnas"] = info["columnas"]
    faltan = [n for n, c in (("descripción", info["mapa"]["descripcion"]), ("precio", info["mapa"]["precio_unitario"])) if not c]
    if faltan and not df.empty:
        out["aviso"] = ("No encontré la columna de " + " ni de ".join(faltan) + " en OrderItems. Indica el nombre en el .env "
                        "(ITEM_COL_DESC, ITEM_COL_PRECIO). Columnas disponibles: " + ", ".join(info["columnas"]) + ".")
    out["lineas"] = [{"sku": x.SKU, "descripcion": x.Descripcion, "qty": x.Qty,
                      "precio": None if pd.isna(x.PrecioUnit) else float(x.PrecioUnit),
                      "monto": None if pd.isna(x.Monto) else float(x.Monto)} for x in df.itertuples()]
    return _sanear(out)


def base_pedidos():
    """(dim, hoy): los pedidos ya modelados, sin tocar las lineas."""
    dim, hoy, _ = _snapshot()
    return dim, hoy


def filtrar_pedidos(filtros: dict) -> pd.DataFrame:
    """Los pedidos que quedan con los mismos filtros del tablero (para calcular otras cifras sobre ellos)."""
    dim, _, _ = _snapshot()
    return _aplicar_filtros(dim, dict(filtros or {}))


def stock_vtex():
    """Stock por codigo SAP (disponible = VTEX - Reservado), o None si no hay datos de stock."""
    _cargar_dim()
    s = _CACHE.get("stock")
    if s is None or len(s) == 0:
        return None
    out = pd.DataFrame({"SKU": s["codigoSap"].astype(str).str.strip(),
                        "VTEX": pd.to_numeric(s["VTEX"], errors="coerce").fillna(0),
                        "Reservado": pd.to_numeric(s["Reservado"], errors="coerce").fillna(0)}).groupby("SKU", as_index=False).sum()
    out["Disponible"] = out["VTEX"] - out["Reservado"]
    return out


def resumen_datos() -> dict:
    """Cobertura de los datos cargados (para que el asistente conteste hasta cuando hay datos)."""
    dim, hoy, _ = _snapshot()
    f = dim["Creation_Date"]
    return {"desde": f.min(), "hasta": f.max(), "pedidos": int(len(dim)), "hoy": hoy, "ultimo_pedido": _CACHE["ultimo_pedido"],
            "consulta": _CACHE["consulta"], "demo": settings.demo}


def lineas_todas():
    """(dim, hoy, lineas normalizadas, info, version) para el asistente."""
    dim, hoy, _ = _snapshot()
    df, info = lineas.todas(_CACHE["version"], dim)
    return dim, hoy, df, info


def obtener(filtros: dict | None = None) -> dict:
    return construir(filtros or {})


def diagnostico() -> dict:
    """Tiempos de la ultima carga (abrir /api/diagnostico en el navegador)."""
    return {"ultima_carga": {"pasos": _PROG["pasos"], "consultas_total_seg": _PROG["total"],
                             "modelo_seg": _PROG["modelo"]},
            "datos_de_las": _CACHE["consulta"], "pedidos_en_memoria": None if _CACHE["dim"] is None else int(len(_CACHE["dim"])),
            "deteccion_rapida": {"error": _MON["error"], "revisado_hace_seg": int(time.time() - _MON["ultima_ok"]) if _MON["ultima_ok"] else None},
            "recargas_completas": _MON["cargas"]}
