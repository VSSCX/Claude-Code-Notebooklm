"""Ejecucion segura de un plan ya validado: calcula con pandas sobre los datos del servidor. Nunca ejecuta SQL ni codigo ajeno."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app import maestra, modelo, queries, servicio, ventas

from . import catalogo
from .texto import lista_es

ESTADO_ETQ = {"no_integrado": "No integrados", "integrado": "Integrados", "cancelado": "Cancelados", "pendiente": "Pendientes",
              "facturado": "Facturados", "vencido": "Con entrega vencida", "sin_despacho": "Facturados sin despacho",
              "alerta_bws": "Alerta BWS", "alerta_post": "Alerta POST Fechado", "alerta_mkp": "Alerta MKP",
              "quiebre": "Pendientes por quiebre de stock"}
STATUS_ES = {"ready-for-handling": "Pendiente (ready-for-handling)", "invoiced": "Facturado (invoiced)",
             "canceled": "Cancelado (canceled)"}
STATUS_CORTO = {"ready-for-handling": "Pendiente", "invoiced": "Facturado", "canceled": "Cancelado"}
DIM_ETQ = {"dia": "Día", "semana": "Semana", "mes": "Mes", "cliente": "Cliente", "canal": "Canal", "bodega": "Bodega",
           "estado": "Estado", "status": "Status", "sla": "SLA Type", "producto": "Producto", "causa": "Causa pendiente", "clasif2": "Clasificación"}
DIM_COL = {"cliente": "SalesChannelName", "canal": "Canal", "bodega": "warehouse", "estado": "Estado Pedido",
           "sla": "SLA_Type", "causa": "Causa Pendiente"}
CRONO = ("dia", "semana", "mes")
COLS_DIM = ["Sequence", "Creation_Date", "SalesChannelName", "Canal", "warehouse", "Estado Pedido", "Status", "SLA_Type",
            "Causa Pendiente", "Total_Value"]
ESPECIALES = {"pct_integracion": ("pct_integracion", "pct", "de integración"), "pct_pendiente": ("pct_pendiente", "pct", "de pedidos pendientes"),
              "antiguedad": ("antig_prom", "dias", "de antigüedad promedio de los pendientes integrados"), "monto_riesgo": ("monto_en_riesgo", "$", "en riesgo"),
              "desfase": ("desfase", "dias", "entre la creación en VTEX y el ingreso a SAP (pedidos integrados)")}


# ------------------------------------------------------------------ periodo y filtros
def rango(plan: dict, hoy: pd.Timestamp):
    p = plan["periodo"] or "mes"
    f = lambda d: d.strftime("%d-%m-%Y")  # noqa: E731
    if p == "hoy":
        return hoy, hoy, f"Hoy ({f(hoy)})"
    if p == "ayer":
        d = hoy - timedelta(days=1)
        return d, d, f"Ayer ({f(d)})"
    if p == "semana":
        ini = hoy - timedelta(days=hoy.weekday())
        return ini, hoy, f"Esta semana ({ini.strftime('%d-%m')} al {hoy.strftime('%d-%m')})"
    if p == "semana_anterior":
        ini = hoy - timedelta(days=hoy.weekday() + 7)
        return ini, ini + timedelta(days=6), f"Semana pasada ({ini.strftime('%d-%m')} al {(ini + timedelta(days=6)).strftime('%d-%m')})"
    if p == "mes_anterior":
        fin = hoy.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin, f"Mes pasado ({fin.strftime('%m-%Y')})"
    if p == "ultimos":
        n = plan["dias"] or 7
        return hoy - timedelta(days=n - 1), hoy, f"Últimos {n} días ({(hoy - timedelta(days=n - 1)).strftime('%d-%m')} al {hoy.strftime('%d-%m')})"
    if p == "todo":
        return None, None, "Todo el período con datos"
    if p == "rango":
        d = pd.Timestamp(plan["desde"]) if plan["desde"] else None
        h = pd.Timestamp(plan["hasta"]) if plan["hasta"] else None
        if d is not None and h is not None and d > h:
            d, h = h, d
        if d is not None and h is not None and d == h:
            return d, h, (f"Anteayer ({f(d)})" if d == hoy - timedelta(days=2) else f(d))
        return d, h, f"Del {f(d) if d is not None else '…'} al {f(h) if h is not None else '…'}"
    return hoy.replace(day=1), hoy, f"Mes en curso ({hoy.strftime('%m-%Y')})"


def _mascara(d: pd.DataFrame, e: str, hoy: pd.Timestamp) -> pd.Series:
    rfh = d["Status"] == "ready-for-handling"
    if e == "no_integrado":
        return d["Estado Ingreso"] == "No ingresado"
    if e == "integrado":
        return d["Estado Ingreso"] == "Ingresado"
    if e == "cancelado":
        return d["Status"] == "canceled"
    if e == "pendiente":
        return rfh
    if e == "facturado":
        return d["Status"] == "invoiced"
    if e == "vencido":
        return rfh & (d["Shipping_Estimate_Date"] < hoy)
    if e == "sin_despacho":
        return d["Facturado Sin Despacho"] == "Facturado sin despacho"
    if e == "alerta_bws":
        return d["Alerta BWS"] == "Atención BWS"
    if e == "alerta_post":
        return d["Alerta POST Fechado"] == "POST Fechado"
    if e == "alerta_mkp":
        return d["Alerta MKP"] == "Atención MKP"
    return rfh & (d["Estado Ingreso"] == "Ingresado") & (d["Causa Pendiente"] == "Quiebre de stock")    # quiebre


def filtrar(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, chips: list, notas: list) -> tuple[pd.DataFrame, str]:
    ini, fin, etq = rango(plan, hoy)
    chips.append(etq)
    fmin = dim["Creation_Date"].min()
    if ini is not None and ini < fmin:
        notas.append(f"Los datos parten el {fmin.strftime('%d-%m-%Y')}; lo anterior no está cargado.")
    d = dim
    if ini is not None:
        d = d[d["Creation_Date"] >= ini]
    if fin is not None:
        d = d[d["Creation_Date"] <= fin]
    for k, col in (("canal", "Canal"), ("cliente", "SalesChannelName"), ("bodega", "warehouse"), ("sla", "SLA_Type")):
        if plan[k]:
            d = d[d[col].isin(plan[k])]
            chips.append(lista_es(plan[k]))
    for e in plan["estado"]:
        d = d[_mascara(d, e, hoy)]
        chips.append(ESTADO_ETQ[e])
    if plan.get("monto_min") is not None:
        d = d[d["Total_Value"] >= plan["monto_min"]]
        chips.append(f"Monto desde ${plan['monto_min']:,.0f}".replace(",", "."))
    if plan.get("monto_max") is not None:
        d = d[d["Total_Value"] <= plan["monto_max"]]
        chips.append(f"Monto hasta ${plan['monto_max']:,.0f}".replace(",", "."))
    if plan.get("edad_min"):
        d = d[d["Creation_Date"] <= hoy - timedelta(days=plan["edad_min"])]
        chips.append(f"Creados hace más de {plan['edad_min']} días")
    if plan["agrupar"] == "causa":
        d = d[_mascara(d, "pendiente", hoy) & (d["Estado Ingreso"] == "Ingresado")]
        notas.append("La causa solo existe para pedidos pendientes ya integrados en SAP.")
    incluye_cancelados = "cancelado" in plan["estado"] or plan["agrupar"] in ("status", "estado")
    if not incluye_cancelados:
        nc = int((d["Status"] == "canceled").sum())
        d = d[d["Status"] != "canceled"]
        chips.append("Sin cancelados")
        if nc:
            notas.append(f"Se excluyeron {nc} pedidos cancelados (pregunta por «cancelados» para verlos).")
    return d, etq


# ------------------------------------------------------------------ medidas
def _num(v):
    return None if v is None or pd.isna(v) else float(v)


def medidas(x: pd.DataFrame, con_lineas: bool) -> dict:
    if con_lineas:
        monto = x["Monto"].sum(min_count=1)
        return {"pedidos": int(x["Sequence"].nunique()), "unidades": float(x["Qty"].sum()), "monto": _num(monto), "lineas": int(len(x))}
    return {"pedidos": int(len(x)), "unidades": float(x["Unidades"].sum()), "monto": float(x["Total_Value"].sum()), "lineas": None}


DIM_PLURAL = {"cliente": "clientes", "canal": "canales", "bodega": "bodegas", "sla": "SLA", "producto": "productos", "estado": "estados",
              "status": "status", "dia": "días", "semana": "semanas", "mes": "meses", "causa": "causas", "clasif2": "clasificaciones"}


def _clave(df: pd.DataFrame, g: str) -> pd.Series:
    if g == "dia":
        return df["Creation_Date"]
    if g == "semana":
        return df["Creation_Date"] - pd.to_timedelta(df["Creation_Date"].dt.weekday, unit="D")
    if g == "mes":
        return df["Creation_Date"].dt.to_period("M").astype(str)
    if g == "status":
        return df["Status"].map(STATUS_ES).fillna(df["Status"])
    if g == "producto":
        return df["Descripcion"].where(df["Descripcion"].astype(bool), df["SKU"])
    return df[DIM_COL[g]]


def _etiqueta_clave(g: str, k) -> str:
    if g == "dia":
        return k.strftime("%d-%m-%Y")
    if g == "semana":
        return "sem. " + k.strftime("%d-%m")
    return "Sin dato" if pd.isna(k) else str(k)


def _especial(plan: dict, base: pd.DataFrame, hoy: pd.Timestamp):
    clave, fmt, unidad = ESPECIALES[plan["metrica"]]
    if clave == "desfase":                                  # promedio de dias entre crear el pedido en VTEX y verlo en SAP
        return _num(base["Dias Desfase"].mean()), fmt, unidad
    base = base.copy()
    base.attrs["hoy"] = hoy
    v = modelo.medidas(base).get(clave)
    return _num(v), fmt, unidad


# ------------------------------------------------------------------ medir / listar
def _preparar_lineas(plan, d, lin_fn, notas):
    """-> (lineas unidas a los pedidos filtrados, productos, mensaje de error)."""
    lin, info = lin_fn()
    prod: list[dict] = []
    if plan["producto"] or plan["sku"]:
        if plan["producto"] and not plan["sku"] and not info["mapa"]["descripcion"]:
            return None, [], ("No puedo buscar por nombre de producto: no encontré la columna de descripción en OrderItems. "
                              "Indica su nombre en el .env (ITEM_COL_DESC). Mientras tanto puedes usar el código SAP (9 dígitos). "
                              "Columnas disponibles: " + ", ".join(info["columnas"]) + ".")
        cat = catalogo.de_union(lin, maestra.cargar()[0])
        skus, aprox, sug = cat.buscar(plan["producto"], plan["sku"])
        if not skus:
            t = f"No encontré productos que coincidan con «{plan['producto'] or plan['sku']}»."
            return None, [], t + (" ¿Quisiste decir: " + "; ".join(sug) + "?" if sug else "")
        prod = [{"sku": s, "descripcion": cat.desc[s]} for s in skus[:8]]
        if aprox:
            notas.append("Coincidencia aproximada: no todas las palabras calzan con un producto.")
        lin = lin[lin["SKU"].isin(skus)]
    return lin.merge(d[COLS_DIM], on="Sequence", how="inner"), prod, None


def _tabla_grupos(plan, base, con_lineas, hoy, metrica):
    g = plan["agrupar"]
    if metrica in ESPECIALES:                               # un indicador del tablero por grupo
        filas = []
        for k, x in base.assign(_k=_clave(base, g)).groupby("_k", dropna=False):
            v, _, _ = _especial({**plan, "metrica": metrica}, x.drop(columns="_k"), hoy)
            filas.append((k, v, len(x)))
        fm = ESPECIALES[metrica][1]
        mayor_primero = plan["orden"] != "asc"
        filas.sort(key=(lambda r: r[0]) if g in CRONO and not plan["orden"] else (lambda r: (r[1] is None, -(r[1] or 0) if mayor_primero else (r[1] or 0))))
        cols = [{"n": DIM_ETQ[g], "f": "t"}, {"n": {"pct_integracion": "% integración", "pct_pendiente": "% pendiente",
                                                      "antiguedad": "Antigüedad (días)", "monto_riesgo": "Monto en riesgo", "desfase": "Desfase (días)"}[metrica], "f": fm}, {"n": "Pedidos", "f": "n"}]
        return cols, [[_etiqueta_clave(g, k), v, n] for k, v, n in filas], len(filas)
    k = _clave(base, g)
    gr = base.assign(_k=k).groupby("_k", dropna=False)
    if con_lineas:
        t = gr.agg(Pedidos=("Sequence", "nunique"), Unidades=("Qty", "sum"), Monto=("Monto", lambda s: s.sum(min_count=1)), Líneas=("SKU", "size"))
    else:
        t = gr.agg(Pedidos=("Sequence", "size"), Unidades=("Unidades", "sum"), Monto=("Total_Value", "sum"))
    col = {"pedidos": "Pedidos", "unidades": "Unidades", "monto": "Monto", "lineas": "Líneas", "ticket": "Monto"}.get(metrica, "Pedidos")
    if col not in t.columns:
        col = "Pedidos"
    if metrica == "ticket":
        t["Ticket"] = t["Monto"] / t["Pedidos"].where(t["Pedidos"] > 0)
        col = "Ticket"
    t = t.reset_index()
    asc = plan["orden"] == "asc"
    crono = g in CRONO and not plan["orden"]               # "el dia con mas pedidos" es un ranking, no una cronologia
    t = t.sort_values("_k" if crono else col, ascending=True if crono else asc, na_position="last")
    total = len(t)
    top = plan["top"] or {"dia": 31, "semana": 12, "mes": 12}.get(g, 10)
    t = t.tail(top) if crono else t.head(top)
    cols = [{"n": DIM_ETQ[g], "f": "t"}, {"n": "Pedidos", "f": "n"}, {"n": "Unidades", "f": "n"}, {"n": "Monto", "f": "$"}]
    if con_lineas and "Líneas" in t:
        cols.append({"n": "Líneas", "f": "n"})
    if metrica == "ticket":
        cols.append({"n": "Ticket", "f": "$"})
    filas = [[_etiqueta_clave(g, r["_k"]), *[None if pd.isna(r[c["n"]]) else float(r[c["n"]]) for c in cols[1:]]] for _, r in t.iterrows()]
    return cols, filas, total


def _listar(plan, base, con_lineas, cap):
    # lo que se suele pedir (pedido, producto, cantidad, monto) va primero: el panel es angosto y la tabla se desplaza hacia el lado
    if plan["metrica"] == "monto" and plan["orden"] in ("asc", "desc"):            # "los 10 pedidos mas caros"
        b = base.sort_values("Total_Value", ascending=plan["orden"] == "asc")
    else:
        b = base.sort_values(["Creation_Date", "Sequence"], ascending=[False, False])
    total = len(b)
    b = b.head(cap)
    st = b["Status"].map(STATUS_CORTO).fillna(b["Status"]).tolist()
    if con_lineas:
        cols = [{"n": "Pedido", "f": "p"}, {"n": "Producto", "f": "t"}, {"n": "Cant.", "f": "n"}, {"n": "Monto", "f": "$"},
                {"n": "Código SAP", "f": "t"}, {"n": "Status", "f": "t"}, {"n": "Cliente", "f": "t"}, {"n": "Fecha", "f": "d"}]
        filas = [[sq, desc, float(q), _num(m), sku, s, c, f.strftime("%Y-%m-%d")] for sq, f, s, c, sku, desc, q, m in
                 zip(b["Sequence"], b["Creation_Date"], st, b["SalesChannelName"], b["SKU"], b["Descripcion"], b["Qty"], b["Monto"])]
    else:
        cols = [{"n": "Pedido", "f": "p"}, {"n": "Unidades", "f": "n"}, {"n": "Monto", "f": "$"}, {"n": "Status", "f": "t"},
                {"n": "Cliente", "f": "t"}, {"n": "Bodega", "f": "t"}, {"n": "Fecha", "f": "d"}]
        filas = [[sq, float(u), float(m), s, c, w, f.strftime("%Y-%m-%d")] for sq, f, s, c, w, u, m in
                 zip(b["Sequence"], b["Creation_Date"], st, b["SalesChannelName"], b["warehouse"], b["Unidades"], b["Total_Value"])]
    return cols, filas, total


def _pct_estado(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp) -> dict:
    """% de los pedidos del periodo que estan en el estado pedido (cancelados, facturados, vencidos). El total INCLUYE cancelados."""
    chips: list[str] = []
    notas: list[str] = []
    d, etq = filtrar({**plan, "estado": [], "agrupar": "status", "monto_min": plan.get("monto_min"), "monto_max": plan.get("monto_max")}, dim, hoy, chips, notas)
    m = pd.Series(True, index=d.index)
    for e in plan["estado"]:
        m &= _mascara(d, e, hoy)
    n, tot = int(m.sum()), len(d)
    etiqueta = lista_es([ESTADO_ETQ[e].lower() for e in plan["estado"]])
    notas.append(f"{n} de {tot} pedidos del período (el total incluye cancelados).")
    return {"ok": True, "tipo": "valor", "metrica": "pct_estado", "chips": chips + [f"% {etiqueta}"], "notas": notas, "productos": [], "etiqueta": etq, "tabla": None,
            "comparacion": None, "resumen": {"pedidos": tot, "unidades": 0.0, "monto": 0.0, "lineas": None}, "con_lineas": False,
            "valor": (n / tot) if tot else None, "formato": "pct", "unidad": f"de los pedidos están {etiqueta}"}


def _clasif2_tabla(plan: dict, d: pd.DataFrame, lin_fn, notas: list):
    """Ventas (monto del pedido repartido por linea, igual que el grafico) por Clasif2 de la maestra."""
    mae, err, _ = maestra.cargar()
    if mae is None:
        return None, "No puedo agrupar por clasificación: " + (err or "no hay maestra de productos cargada.")
    lin, _ = lin_fn()
    m = ventas.repartir(lin, d[["Sequence", "Total_Value"]], mae)
    g = m.groupby("Clasif2").agg(Pedidos=("Sequence", "nunique"), Unidades=("Qty", "sum"), Monto=("Venta", "sum")).reset_index()
    return g, None


def medir_o_listar(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn) -> dict:
    notas: list[str] = []
    chips: list[str] = []
    accion = plan["accion"] or "medir"
    if plan["metrica"] == "pct_estado" and plan["estado"]:
        return _pct_estado(plan, dim, hoy)
    d, etq = filtrar(plan, dim, hoy, chips, notas)
    if plan["agrupar"] == "clasif2":
        g, err = _clasif2_tabla(plan, d, lin_fn, notas)
        if g is None:
            return {"ok": False, "texto": err, "chips": chips, "notas": notas}
        col = {"pedidos": "Pedidos", "unidades": "Unidades"}.get(plan["metrica"], "Monto")
        g = g.sort_values(col, ascending=plan["orden"] == "asc").reset_index(drop=True)
        total = len(g)
        g = g.head(plan["top"] or 30)
        cols = [{"n": "Clasificación", "f": "t"}, {"n": "Pedidos", "f": "n"}, {"n": "Unidades", "f": "n"}, {"n": "Monto", "f": "$"}]
        filas = [[str(r["Clasif2"]), float(r["Pedidos"]), float(r["Unidades"]), float(r["Monto"])] for _, r in g.iterrows()]
        notas.append("La venta es el monto del pedido repartido entre las clasificaciones de sus líneas (igual que el gráfico «Ventas por Clasif2»); "
                     "los pedidos que cuentan en varias clasificaciones se suman en cada una." if col != "Monto" else
                     "La venta es el monto del pedido repartido entre las clasificaciones de sus líneas (igual que el gráfico «Ventas por Clasif2»).")
        tot_monto, tot_ped = float(d["Total_Value"].sum()), int(len(d))
        return {"ok": True, "tipo": "tabla", "metrica": plan["metrica"] or "monto", "chips": chips + ["Por clasificación"], "notas": notas, "productos": [], "etiqueta": etq,
                "tabla": {"cols": cols, "filas": filas}, "total_filas": total, "agrupar": "clasif2", "comparacion": None,
                "resumen": {"pedidos": tot_ped, "unidades": float(d["Unidades"].sum()), "monto": tot_monto, "lineas": None}, "con_lineas": True,
                "valor": tot_monto if col == "Monto" else (float(g[col].sum()) if len(g) else 0.0), "formato": "$" if col == "Monto" else "n",
                "unidad": "" if col == "Monto" else col.lower()}
    metrica = plan["metrica"] or ("unidades" if (plan["producto"] or plan["sku"] or plan["agrupar"] == "producto") else "pedidos")
    if metrica == "distintos" and not plan["agrupar"]:
        plan = {**plan, "agrupar": "cliente"}
    ranking_pedidos = accion == "listar" and metrica == "monto" and plan["orden"] in ("asc", "desc") and not (plan["producto"] or plan["sku"])
    con_lineas = bool(plan["producto"] or plan["sku"]) or metrica == "lineas" or plan["agrupar"] == "producto" or (accion == "listar" and not ranking_pedidos)
    base, productos = d, []
    if con_lineas:
        try:
            m, productos, err = _preparar_lineas(plan, d, lin_fn, notas)
        except Exception as e:  # noqa: BLE001
            m, err = None, "No pude leer las líneas de los pedidos (OrderItems): " + str(e)[:160]
            if plan["producto"] or plan["sku"] or metrica == "lineas" or plan["agrupar"] == "producto":
                return {"ok": False, "texto": err, "chips": chips, "notas": notas}
            notas.append(err)
            con_lineas = False
        else:
            if err:
                return {"ok": False, "texto": err, "chips": chips, "notas": notas, "sin_producto": True}
            base = m
        if productos:
            chips.append(productos[0]["descripcion"] + (f" y {len(productos) - 1} más" if len(productos) > 1 else ""))
    if metrica in ("monto", "ticket") and con_lineas and base["Monto"].isna().all() and len(base):
        return {"ok": False, "chips": chips, "notas": notas,
                "texto": "No encontré la columna de precio en OrderItems, así que no puedo calcular montos por producto. Indica su nombre en el .env (ITEM_COL_PRECIO)."}

    resumen = medidas(base, con_lineas) if len(base) else {"pedidos": 0, "unidades": 0.0, "monto": 0.0, "lineas": 0 if con_lineas else None}
    res = {"ok": True, "tipo": "valor", "metrica": metrica, "chips": chips, "notas": notas, "productos": productos, "etiqueta": etq,
           "tabla": None, "comparacion": None, "resumen": resumen, "con_lineas": con_lineas}
    if metrica in ESPECIALES:
        v, fm, unidad = _especial({**plan, "metrica": metrica}, d, hoy)
        res.update(valor=v, formato=fm, unidad=unidad)
    elif metrica == "ticket":
        res.update(valor=_num(resumen["monto"] / resumen["pedidos"]) if resumen["pedidos"] and resumen["monto"] is not None else None,
                   formato="$", unidad="de ticket promedio por pedido")
    elif metrica == "upp":
        res.update(valor=(resumen["unidades"] / resumen["pedidos"]) if resumen["pedidos"] else None, formato="n1", unidad="unidades por pedido en promedio")
    elif metrica == "distintos":
        res.update(valor=0.0, formato="n", unidad="distintos")
    else:
        res.update(valor=resumen[metrica] if resumen[metrica] is not None else 0.0, formato="$" if metrica == "monto" else "n",
                   unidad={"unidades": "unidades", "pedidos": "pedidos", "monto": "", "lineas": "líneas"}[metrica])

    if accion == "listar":
        cap = plan["top"] or 100
        cols, filas, total = _listar(plan, base, con_lineas, min(cap, 300))
        res.update(tipo="lista", tabla={"cols": cols, "filas": filas}, total_filas=total, metrica="pedidos", valor=float(resumen["pedidos"]), formato="n", unidad="pedidos")
        if total > len(filas):
            notas.append(f"Se muestran {len(filas)} de {total} filas ({'los de mayor monto primero' if ranking_pedidos else 'más recientes primero'}). Acota el período o los filtros para ver el resto.")
    else:
        g = plan["agrupar"] or ("producto" if len(productos) > 1 else None)
        if g and len(base):
            plan2 = {**plan, "agrupar": g}
            cols, filas, total = _tabla_grupos(plan2, base, con_lineas, hoy, metrica)
            res.update(tipo="tabla", tabla={"cols": cols, "filas": filas}, total_filas=total, agrupar=g)
            if metrica == "distintos":
                res.update(valor=float(total), unidad=f"{DIM_PLURAL.get(g, g)} distintos con pedidos")
            if g not in CRONO and total > len(filas) and plan["top"] != 1:
                notas.append(f"Se muestran los primeros {len(filas)} de {total}.")
        if plan["comparar"]:
            res["comparacion"] = _comparar(plan, dim, hoy, lin_fn, res)
    return res


def _comparar(plan, dim, hoy, lin_fn, res):
    ini, fin, _ = rango(plan, hoy)
    if ini is None or fin is None:
        res["notas"].append("No se puede comparar el período «todo».")
        return None
    largo = (fin - ini).days + 1
    pini, pfin = ini - timedelta(days=largo), ini - timedelta(days=1)
    if plan["periodo"] in ("mes_anterior", "rango") and ini.day == 1 and (fin + timedelta(days=1)).day == 1:    # un mes calendario completo: contra el mes de antes
        pini = (ini - pd.offsets.MonthBegin(1)).normalize()
        pfin = ini - timedelta(days=1)
    elif plan["periodo"] == "mes":                                  # el mes en curso se compara con los mismos dias del mes anterior
        pini = (ini - pd.offsets.MonthBegin(1)).normalize()
        pfin = min(pini + timedelta(days=largo - 1), ini - timedelta(days=1))
    elif plan["periodo"] == "semana":                             # la semana en curso, con los mismos dias de la semana pasada
        pini = ini - timedelta(days=7)
        pfin = pini + timedelta(days=largo - 1)
    p2 = {**plan, "periodo": "rango", "desde": pini.strftime("%Y-%m-%d"), "hasta": pfin.strftime("%Y-%m-%d"), "agrupar": None, "comparar": False, "accion": "medir"}
    fmin = dim["Creation_Date"].min()
    if pfin < fmin:                                               # el periodo anterior es anterior a los datos cargados
        res["notas"].append(f"No puedo comparar: el período anterior ({pini.strftime('%d-%m')} al {pfin.strftime('%d-%m')}) es anterior a los datos cargados (desde el {fmin.strftime('%d-%m-%Y')}).")
        return None
    if pini < fmin:
        res["notas"].append(f"El período anterior está incompleto: los datos parten el {fmin.strftime('%d-%m-%Y')}.")
    r2 = medir_o_listar(p2, dim, hoy, lin_fn)
    if not r2.get("ok") or r2.get("valor") is None or res.get("valor") is None:
        return None
    ant, act = r2["valor"], res["valor"]
    return {"etiqueta": f"{pini.strftime('%d-%m')} al {pfin.strftime('%d-%m')}", "anterior": ant, "delta": act - ant,
            "pct": None if not ant else (act - ant) / ant}


# ------------------------------------------------------------------ stock
def stock(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn, stock_fn) -> dict:
    """Stock VTEX (VTEX - Reservado) por codigo SAP. Con producto: se busca en el catalogo (lineas de pedidos + maestra), se toman sus
    codigos SAP y se cruza con la tabla de stock, igual que las ventas. Sin producto: lo que esta sin stock y tiene pedidos pendientes."""
    notas: list[str] = []
    st = stock_fn()
    if st is None or st.empty:
        e = servicio.estado_stock()
        if e.get("cargando"):
            return {"ok": False, "chips": [], "notas": [], "texto": f"El stock VTEX todavía se está consultando a la base (lleva {e['segundos_corriendo'] or 0} s; "
                    f"se corta a los {e['timeout_seg']} s). Vuelve a preguntar en un momento."}
        return {"ok": False, "chips": [], "notas": [], "texto": "No tengo datos de stock VTEX cargados (consulta de bi_vtex_stock del ODS)."
                + (f" Error al leerla: {e['error']}" if e["error"] else " La tabla vino vacía.")}
    lin, _ = lin_fn()
    cat = catalogo.de_union(lin, maestra.cargar()[0])
    pend = lin.merge(dim.loc[dim["Status"] == "ready-for-handling", ["Sequence"]], on="Sequence").groupby("SKU")["Qty"].sum()
    rec = lin.merge(dim.loc[(dim["Status"] != "canceled") & (dim["Creation_Date"] >= hoy - timedelta(days=13)), ["Sequence"]], on="Sequence")
    diaria = rec.groupby("SKU")["Qty"].sum() / 14                       # venta diaria promedio de los ultimos 14 dias
    chips = ["Stock VTEX = VTEX − Reservado"] + ([f"Stock al {queries.INFO_STOCK['fecha']}"] if queries.INFO_STOCK.get("fecha") else [])
    productos: list[dict] = []
    modo = plan.get("stock_modo")
    if plan["producto"] or plan["sku"]:
        skus, aprox, sug = cat.buscar(plan["producto"], plan["sku"])
        if not skus:
            t = f"No encontré productos que coincidan con «{plan['producto'] or plan['sku']}»."
            return {"ok": False, "texto": t + (" ¿Quisiste decir: " + "; ".join(sug) + "?" if sug else ""), "chips": chips, "notas": [], "sin_producto": True}
        productos = [{"sku": k, "descripcion": cat.desc[k]} for k in skus[:8]]
        if aprox:
            notas.append("Coincidencia aproximada: no todas las palabras calzan con un producto.")
        s = pd.DataFrame({"SKU": skus}).merge(st, on="SKU", how="left")           # un renglon por producto, haya o no stock cargado
        s["Producto"], s["Pend"] = s["SKU"].map(cat.desc).fillna(""), s["SKU"].map(pend).fillna(0.0)
        s["Cobertura"] = s["Disponible"] / s["SKU"].map(diaria)
        chips.append(productos[0]["descripcion"] + (f" y {len(productos) - 1} más" if len(productos) > 1 else ""))
        sin_dato = s[s["Disponible"].isna()]
        if len(sin_dato):
            ej = ", ".join(map(str, st["SKU"].head(3)))
            notas.append(f"{len(sin_dato)} producto(s) no aparecen en la tabla de stock con su código SAP ({', '.join(sin_dato['SKU'].head(3))}). "
                         f"Códigos de ejemplo de esa tabla: {ej}. Si el formato difiere, avísame.")
        titulo, valor = "unidades disponibles", float(s["Disponible"].sum(skipna=True))
        s = s.sort_values("Disponible", na_position="last")
        if modo in ("poco", "cobertura"):
            s = s.sort_values("Cobertura", na_position="last")
    else:
        s = st.assign(Pend=st["SKU"].map(pend).fillna(0.0), Producto=st["SKU"].map(cat.desc).fillna(""))
        s["Cobertura"] = s["Disponible"] / s["SKU"].map(diaria)
        vende = s["SKU"].map(diaria).fillna(0) > 0
        if modo == "todo":
            chips.append("Todos los productos")
            titulo, valor = "unidades disponibles en total", float(s["Disponible"].sum())
            s = s.sort_values("Disponible", ascending=False)
            notas.append(f"{int((s['Disponible'] <= 0).sum())} de {len(s)} productos están sin stock disponible.")
        elif modo in ("poco", "cobertura"):
            chips.append("Menos días de cobertura primero")
            conv = s[(s["Disponible"] > 0) & vende].sort_values("Cobertura")
            s = conv if modo == "cobertura" else conv[conv["Cobertura"] < 14]
            titulo, valor = ("productos con menos de 14 días de cobertura" if modo == "poco" else "productos con venta y stock (ordenados por cobertura)"), float(len(s))
            notas.append("Cobertura = stock disponible ÷ venta diaria de los últimos 14 días. Los productos sin stock no se incluyen aquí: pregunta «¿qué productos no tienen stock?».")
        else:
            sin = s[(s["Disponible"] <= 0)]
            con_demanda = sin[sin["Pend"] > 0]
            s = (con_demanda if len(con_demanda) else sin).sort_values("Pend", ascending=False)
            chips.append("Sin stock disponible")
            titulo, valor = "productos sin stock disponible" + (" con pedidos pendientes" if len(con_demanda) else ""), float(len(s))
    total = len(s)
    s = s.head(plan["top"] or 30)
    num = lambda v: None if pd.isna(v) else float(v)  # noqa: E731
    cols = [{"n": "Código SAP", "f": "t"}, {"n": "Producto", "f": "t"}, {"n": "Stock VTEX", "f": "n"}, {"n": "Reservado", "f": "n"},
            {"n": "Disponible", "f": "n"}, {"n": "Unid. en pedidos pendientes", "f": "n"}, {"n": "Cobertura (días, venta 14 d)", "f": "n"}]
    cob = lambda v: None if pd.isna(v) or v == float("inf") else round(float(v), 1)  # noqa: E731
    filas = [[a, b, num(c), num(d), num(e), float(f), cob(g)] for a, b, c, d, e, f, g in
             zip(s["SKU"], s["Producto"], s["VTEX"], s["Reservado"], s["Disponible"], s["Pend"], s["Cobertura"])]
    if total > len(filas):
        notas.append(f"Se muestran {len(filas)} de {total}.")
    return {"ok": True, "tipo": "stock", "valor": valor, "formato": "n", "unidad": titulo, "tabla": {"cols": cols, "filas": filas},
            "chips": chips, "notas": notas, "productos": productos, "etiqueta": "Stock actual", "resumen": None, "comparacion": None, "metrica": "stock"}


# ------------------------------------------------------------------ alertas y anomalias
def alertas(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn, stock_fn) -> dict:
    """Revisa el tablero y dice que esta fuera de lo normal: volumen, cancelaciones, pendientes, integracion y quiebre de stock proyectado."""
    filas: list[list] = []
    sev = {"alta": 0, "media": 1, "baja": 2}
    d = dim[dim["Status"] != "canceled"]
    ayer = hoy - timedelta(days=1)

    # 1) volumen de ayer contra el mismo dia de la semana (4 semanas previas)
    tipicos = [int(((d["Creation_Date"] >= ayer - timedelta(days=7 * k)) & (d["Creation_Date"] < ayer - timedelta(days=7 * k) + timedelta(days=1))).sum()) for k in range(1, 5)]
    n_ayer = int(((d["Creation_Date"] >= ayer) & (d["Creation_Date"] < hoy)).sum())
    tip = [t for t in tipicos if t > 0]
    if len(tip) >= 2:
        med = sum(tip) / len(tip)
        var = n_ayer / med - 1
        if abs(var) >= .3:
            filas.append(["alta" if abs(var) >= .5 else "media", "Volumen de pedidos",
                          f"Ayer hubo {n_ayer} pedidos, {abs(var) * 100:.0f}% {'más' if var > 0 else 'menos'} que un {_dia(ayer)} típico (~{med:.0f})."])

    # 2) tasa de cancelacion: ultimos 7 dias contra los 28 anteriores
    def tasa(a, b):
        x = dim[(dim["Creation_Date"] >= a) & (dim["Creation_Date"] < b)]
        return (float((x["Status"] == "canceled").mean()), len(x)) if len(x) >= 20 else (None, len(x))
    r7, n7 = tasa(hoy - timedelta(days=6), hoy + timedelta(days=1))
    r28, _ = tasa(hoy - timedelta(days=34), hoy - timedelta(days=6))
    if r7 is not None and r28 is not None and r7 > r28 * 1.3 and r7 - r28 >= .01:
        filas.append(["alta" if r7 > r28 * 2 else "media", "Cancelaciones",
                      f"Cancelación de los últimos 7 días: {r7 * 100:.1f}% (los 28 días previos: {r28 * 100:.1f}%)."])

    # 3) pendientes, integracion y facturacion
    rfh = d["Status"] == "ready-for-handling"
    venc = int((rfh & (d["Shipping_Estimate_Date"] < hoy)).sum())
    if venc:
        filas.append(["alta" if venc >= 20 else "media", "Entrega vencida", f"{venc} pedidos pendientes ya pasaron su fecha de entrega estimada."])
    viejos = int(((d["Estado Ingreso"] == "No ingresado") & (d["Creation_Date"] < hoy - timedelta(days=1)) & (d["Status"] != "invoiced")).sum())
    if viejos:
        filas.append(["media", "Integración SAP", f"{viejos} pedidos creados antes de ayer siguen sin ingresar a SAP."])
    sd = int((d["Facturado Sin Despacho"] == "Facturado sin despacho").sum())
    if sd:
        filas.append(["media", "Facturado sin despacho", f"{sd} pedidos están facturados en SAP pero pendientes en VTEX."])
    quiebre = int((rfh & (d["Causa Pendiente"] == "Quiebre de stock")).sum())
    if quiebre:
        filas.append(["media", "Pendientes por quiebre", f"{quiebre} pedidos pendientes esperan por falta de stock."])

    # 4) stock: sin stock con demanda, y cobertura corta segun la venta de los ultimos 14 dias
    notas: list[str] = []
    try:
        st = stock_fn()
        lin, _ = lin_fn()
        if st is None or st.empty:
            notas.append("No hay datos de stock cargados: no se revisó el riesgo de quiebre.")
        else:
            cat = catalogo.de_union(lin, maestra.cargar()[0])
            rec = lin.merge(d.loc[d["Creation_Date"] >= hoy - timedelta(days=13), ["Sequence"]], on="Sequence")
            diaria = rec.groupby("SKU")["Qty"].sum() / 14
            pend = lin.merge(d.loc[rfh, ["Sequence"]], on="Sequence").groupby("SKU")["Qty"].sum()
            s = st.assign(dia=st["SKU"].map(diaria).fillna(0.0), pend=st["SKU"].map(pend).fillna(0.0))
            s["cob"] = (s["Disponible"].clip(lower=0) / s["dia"]).where(s["dia"] > 0)
            sin = s[(s["Disponible"] <= 0) & ((s["pend"] > 0) | (s["dia"] > 0))].sort_values("pend", ascending=False)
            for _, r in sin.head(5).iterrows():
                filas.append(["alta", "Sin stock", f"{cat.desc.get(r['SKU'], r['SKU'])} ({r['SKU']}): sin stock disponible, {r['pend']:.0f} unid. en pedidos pendientes."])
            corto = s[(s["Disponible"] > 0) & (s["cob"] < 7)].sort_values("cob")
            for _, r in corto.head(5).iterrows():
                filas.append(["media", "Quiebre próximo", f"{cat.desc.get(r['SKU'], r['SKU'])} ({r['SKU']}): {r['Disponible']:.0f} unid. alcanzan para ~{r['cob']:.1f} días."])
            if len(sin) > 5 or len(corto) > 5:
                notas.append(f"Hay {len(sin)} productos sin stock y {len(corto)} con menos de 7 días de cobertura; se muestran los 5 más urgentes de cada grupo.")
    except Exception as e:  # noqa: BLE001
        notas.append("No pude revisar el stock: " + str(e)[:100])

    filas.sort(key=lambda f: sev[f[0]])
    if not filas:
        texto = "Revisé volumen, cancelaciones, pendientes, integración y stock: no veo nada fuera de lo normal."
    else:
        texto = f"Encontré {len(filas)} punto(s) para revisar; {sum(f[0] == 'alta' for f in filas)} de severidad alta."
    cols = [{"n": "Severidad", "f": "t"}, {"n": "Tema", "f": "t"}, {"n": "Detalle", "f": "t"}]
    return {"ok": True, "tipo": "alertas", "texto": texto, "valor": float(len(filas)), "formato": "n", "unidad": "puntos a revisar",
            "tabla": {"cols": cols, "filas": filas}, "chips": ["Revisión automática", f"Datos hasta {hoy.strftime('%d-%m-%Y')}"],
            "notas": notas, "etiqueta": "Alertas", "resumen": None, "comparacion": None, "metrica": "alertas"}


def _dia(d: pd.Timestamp) -> str:
    return ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][d.weekday()]


# ------------------------------------------------------------------ resumen del periodo y productos sin ventas
def resumen(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn) -> dict:
    """«¿Como vamos?»: los indicadores clave del periodo frente al periodo anterior de igual largo."""
    p = {**plan, "periodo": plan["periodo"] or "mes", "estado": [], "agrupar": None, "metrica": None, "accion": "medir"}
    ini, fin, etq = rango(p, hoy)
    chips: list[str] = []
    notas: list[str] = []

    def kpis(a, b):
        pl = {**p, "periodo": "rango", "desde": a.strftime("%Y-%m-%d"), "hasta": b.strftime("%Y-%m-%d")} if a is not None else p
        todos, _ = filtrar({**pl, "agrupar": "status"}, dim, hoy, [], [])
        d = todos[todos["Status"] != "canceled"]
        n, can = len(d), int((todos["Status"] == "canceled").sum())
        rfh = d["Status"] == "ready-for-handling"
        return {"Pedidos": n, "Ventas": float(d["Total_Value"].sum()), "Unidades": float(d["Unidades"].sum()),
                "Ticket promedio": float(d["Total_Value"].sum() / n) if n else None,
                "Cancelados": can, "% cancelación": (can / len(todos)) if len(todos) else None,
                "% integración": float((d["Estado Ingreso"] == "Ingresado").mean()) if n else None,
                "Pendientes": int(rfh.sum()), "Con entrega vencida": int((rfh & (d["Shipping_Estimate_Date"] < hoy)).sum()),
                "Facturados sin despacho": int((d["Facturado Sin Despacho"] == "Facturado sin despacho").sum())}
    act = kpis(ini, fin) if ini is not None else kpis(None, None)
    ant = None
    if ini is not None and fin is not None:
        largo = (fin - ini).days + 1
        ant = kpis(ini - timedelta(days=largo), ini - timedelta(days=1))
    fmt = {"Ventas": "$", "Ticket promedio": "$", "% cancelación": "pct", "% integración": "pct"}
    filas = []
    for k, v in act.items():
        a = ant[k] if ant else None
        var = None if (a in (None, 0) or v is None or fmt.get(k) == "pct") else (v - a) / a
        filas.append([k, v, a, var, fmt.get(k, "n")])
    cols = [{"n": "Indicador", "f": "t"}, {"n": "Actual", "f": "x"}, {"n": "Período anterior", "f": "x"}, {"n": "Variación", "f": "pct"}]
    if ini is not None:
        chips.append(f"Comparado con el período anterior de {(fin - ini).days + 1} día(s)")
    p_ = lambda x: None if x is None else float(x)  # noqa: E731
    tabla = [[k, p_(v), p_(a), p_(var), f] for k, v, a, var, f in filas]
    mi = lambda x: f"{x:,.0f}".replace(",", ".")  # noqa: E731
    t = (f"{etq}: {mi(act['Pedidos'])} pedidos, {_peso(act['Ventas'])} en ventas, ticket {_peso(act['Ticket promedio'])}. "
         f"{mi(act['Cancelados'])} cancelados ({_pctf(act['% cancelación'])}), integración {_pctf(act['% integración'])}, "
         f"{mi(act['Pendientes'])} pendientes ({mi(act['Con entrega vencida'])} con entrega vencida).")
    if ant and ant["Pedidos"]:
        v = act["Pedidos"] / ant["Pedidos"] - 1
        t += (f" Pedidos {'+' if v >= 0 else '−'}{abs(v) * 100:.1f}%".replace(".", ",") + " frente al período anterior"
              + (f" y ventas {'+' if act['Ventas'] >= ant['Ventas'] else '−'}{abs(act['Ventas'] / ant['Ventas'] - 1) * 100:.1f}%".replace(".", ",") if ant["Ventas"] else "") + ".")
    return {"ok": True, "tipo": "resumen", "texto": t, "valor": float(act["Pedidos"]), "formato": "n", "unidad": "pedidos", "tabla": {"cols": cols, "filas": tabla, "formato_celda": True},
            "chips": chips, "notas": notas, "etiqueta": etq, "resumen": None, "comparacion": None, "metrica": "resumen", "productos": []}


def _peso(v) -> str:
    return "sin dato" if v is None else "$" + f"{v:,.0f}".replace(",", ".")


def _pctf(v) -> str:
    return "sin dato" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def sin_ventas(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn, stock_fn) -> dict:
    """Productos del catalogo (lineas + maestra) que no se vendieron en el periodo."""
    chips: list[str] = []
    notas: list[str] = []
    g = plan["agrupar"]
    d, etq = filtrar({**plan, "estado": [e for e in plan["estado"] if e != "cancelado"], "agrupar": None}, dim, hoy, chips, notas)
    if g in ("cliente", "canal", "bodega", "sla"):               # "que clientes no compraron": valores conocidos sin pedidos en el periodo
        col = DIM_COL[g]
        ult = dim.groupby(col)["Creation_Date"].max()
        faltan = sorted(set(dim[col].dropna().unique()) - set(d[col].dropna().unique()))
        filas = [[str(v), ult[v].strftime("%d-%m-%Y")] for v in faltan]
        texto = (f"{etq}: " + (f"{len(filas)} {DIM_PLURAL[g]} sin pedidos: {', '.join(r[0] for r in filas[:8])}." if filas
                              else f"todos los {DIM_PLURAL[g]} tuvieron pedidos en el período."))
        return {"ok": True, "tipo": "sin_ventas", "texto": texto, "valor": float(len(filas)), "formato": "n", "unidad": f"{DIM_PLURAL[g]} sin pedidos",
                "tabla": {"cols": [{"n": DIM_ETQ[g], "f": "t"}, {"n": "Último pedido", "f": "t"}], "filas": filas}, "chips": chips, "notas": notas,
                "etiqueta": etq, "resumen": None, "comparacion": None, "metrica": "sin_ventas", "productos": []}
    lin, _ = lin_fn()
    mae = maestra.cargar()[0]
    cat = catalogo.de_union(lin, mae)
    vendidos = set(lin.merge(d[["Sequence"]], on="Sequence")["SKU"])
    faltan = [k for k in cat.desc if k not in vendidos and k]
    st = stock_fn()
    disp = dict(zip(st["SKU"], st["Disponible"])) if st is not None and not st.empty else {}
    filas = [[k, cat.desc[k], disp.get(k)] for k in faltan]
    filas.sort(key=lambda r: (r[2] is None, -(r[2] or 0)))
    cols = [{"n": "Código SAP", "f": "t"}, {"n": "Producto", "f": "t"}, {"n": "Stock disponible", "f": "n"}]
    total = len(filas)
    filas = filas[:plan["top"] or 30]
    if total > len(filas):
        notas.append(f"Se muestran {len(filas)} de {total}; los de más stock primero (más capital detenido).")
    if mae is None:
        notas.append("Sin maestra de productos solo se revisan los productos que alguna vez aparecieron en pedidos.")
    texto = (f"{etq}: {total} producto{'s' if total != 1 else ''} del catálogo sin ventas." if total
             else f"{etq}: todos los productos del catálogo tuvieron ventas.")
    return {"ok": True, "tipo": "sin_ventas", "texto": texto, "valor": float(total), "formato": "n", "unidad": "productos sin ventas", "tabla": {"cols": cols, "filas": filas},
            "chips": chips + ["Sin ventas en el período"], "notas": notas, "etiqueta": etq, "resumen": None, "comparacion": None, "metrica": "sin_ventas", "productos": [],
            "total_filas": total, "agrupar": "producto"}
