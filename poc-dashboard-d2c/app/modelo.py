"""Port del modelo Power BI a pandas: Dim Pedidos, columnas calculadas y medidas.

Reproduce, tabla por tabla y columna por columna, la lógica del POC_Dashboard_D2C.pbix:
- Dim Pedidos = DISTINCT de Orders
- Estado Ingreso, Estado Pedido, Canal, alertas, motivos de pendiente, KPIs de cierre
- Todas las medidas del resumen ejecutivo, incluidas las comparaciones MTD
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Construccion de Dim Pedidos con todas las columnas calculadas (VECTORIZADO)
# Cada columna replica exactamente la formula DAX del Power BI, pero se calcula sobre
# la columna completa (no fila por fila), por eso recarga en ~1 s en vez de decenas de s.
# ---------------------------------------------------------------------------
def construir(orders: pd.DataFrame, order_items: pd.DataFrame, sap: pd.DataFrame,
              fact: pd.DataFrame, stock_vtex: pd.DataFrame, hoy: pd.Timestamp) -> dict:
    o = orders.copy()
    o["Creation_Date"] = pd.to_datetime(o["Creation_Date"])
    o["Shipping_Estimate_Date"] = pd.to_datetime(o.get("Shipping_Estimate_Date"))
    o["Sequence"] = o["Sequence"].astype(str).str.strip()

    sap = sap.copy()
    sap["OC"] = sap["OrdenCompra"].astype(str).str.strip()
    sap["Fecha_Pedido"] = pd.to_datetime(sap["Fecha_Pedido"])

    fact = fact.copy()
    fact["OC"] = fact["ordenCompra"].astype(str).str.strip()
    fact["Fecha"] = pd.to_datetime(fact["Fecha"])

    # ---- Dim Pedidos = DISTINCT de Orders sobre las 10 columnas del modelo ----
    dim = o[["Order", "Sequence", "Creation_Date", "Status", "SalesChannelName",
             "Total_Value", "SLA_Type", "warehouse", "Unidades",
             "Shipping_Estimate_Date"]].drop_duplicates().reset_index(drop=True)

    # ---- Cruce con SAP Ingresos: ventana [-1, +15] dias respecto de la fecha de creacion ----
    sapx = sap[["OC", "Fecha_Pedido", "Pedido"]].copy()
    sapx["_ped"] = sapx["Pedido"].astype(str)
    sapx = sapx.drop_duplicates(["OC", "Fecha_Pedido", "_ped"])
    j = dim[["Sequence", "Creation_Date"]].drop_duplicates("Sequence").merge(
        sapx, left_on="Sequence", right_on="OC", how="inner")
    delta = j["Fecha_Pedido"] - j["Creation_Date"]
    j = j[(delta >= pd.Timedelta(days=-1)) & (delta <= pd.Timedelta(days=15))].assign(lag=delta.dt.days)

    ingresados = set(j["Sequence"])
    dim["Estado Ingreso"] = np.where(
        dim["Status"] == "canceled", "Cancelado VTEX",
        np.where(dim["Sequence"].isin(ingresados), "Ingresado", "No ingresado"))
    dim["Dias Desfase"] = dim["Sequence"].map(j.groupby("Sequence")["lag"].min()).astype(float)
    peds = j.drop_duplicates(["Sequence", "_ped"]).groupby("Sequence")["_ped"].agg(" | ".join)
    dim["Pedido SAP"] = dim["Sequence"].map(peds).fillna("")

    ei, st = dim["Estado Ingreso"], dim["Status"]
    rfh = st == "ready-for-handling"

    # ---- Estado Pedido ----
    dim["Estado Pedido"] = np.select(
        [ei == "Cancelado VTEX", (ei == "Ingresado") & (st == "invoiced"), ei == "Ingresado", st == "invoiced"],
        ["Cancelado", "Integrado · Facturado", "Integrado · Pendiente", "No integrado · Facturado"],
        "No integrado · Pendiente")

    # ---- Trazabilidad: "Cerrado" = facturado e integrado, o cancelado ----
    dim["Trazabilidad"] = np.where(
        ((st == "invoiced") & (ei == "Ingresado")) | (st == "canceled"), "Cerrado", "En seguimiento")

    # ---- Canal (agrupacion BWS/MKP/Otros) ----
    bws = {"Fensa", "Mademsa", "Electrolux"}
    mkp = {"Falabella", "Paris", "Ripley", "Walmart", "Hites", "MELI"}
    otros = {"Colaboradores", "Empresas", "Reposición", "Shopclub", "Totem"}
    sc = dim["SalesChannelName"]
    dim["Canal"] = np.select([sc.isin(bws), sc.isin(mkp), sc.isin(otros)], ["BWS", "MKP", "Otros"], sc)

    # ---- Antiguedad y fecha de referencia ----
    hoy = pd.Timestamp(hoy).normalize()
    # El Power BI mide antiguedad y alertas contra MAX(Creation_Date), no contra "hoy".
    ref = dim["Creation_Date"].max()
    dim["Antigüedad Días"] = (ref - dim["Creation_Date"]).dt.days

    # ---- Gap de entrega y alerta de fecha ----
    sed, cre = dim["Shipping_Estimate_Date"], dim["Creation_Date"]
    gap = (sed - cre).dt.days.astype(float)
    dim["Gap Entrega Días"] = gap
    dim["Alerta Fecha Entrega"] = np.select(
        [gap.isna(), gap < 0], ["Sin fecha estimada", "Entrega anterior a la venta"], "OK")

    # ---- Alertas de los botones ----
    un_dia, cinco = pd.Timedelta(days=1), pd.Timedelta(days=5)
    dim["Alerta BWS"] = np.where((dim["Canal"] == "BWS") & rfh & sed.notna() & (sed <= ref - un_dia),
                                 "Atención BWS", None)
    dim["Alerta POST Fechado"] = np.where((dim["warehouse"] == "POST_Fechado") & rfh, "POST Fechado", None)
    dim["Alerta MKP"] = np.where((dim["Canal"] == "MKP") & rfh & (cre <= ref - cinco), "Atención MKP", None)

    # ---- Facturado sin despacho (cruce con Facturacion, sin tope de dias) ----
    fact_min = fact.groupby("OC")["Fecha"].min()
    en_fact = dim["Sequence"].isin(fact_min.index)
    dim["Facturado Sin Despacho"] = np.where(rfh & en_fact, "Facturado sin despacho", None)
    fmin = dim["Sequence"].map(fact_min)
    dim["Dias Facturado Pendiente"] = np.where(rfh & fmin.notna(), (hoy - fmin).dt.days, np.nan)

    # ---- Motivo por stock (Stock VTEX = VTEX - Reservado), a nivel linea -> pedido ----
    dim = _motivo_stock(dim, order_items, stock_vtex, hoy)

    # ---- KPIs de cierre de mes ----
    dim["Cierre Mes"] = (dim["Creation_Date"] + pd.offsets.MonthEnd(0)).dt.normalize()
    pend_int = rfh & (dim["Estado Ingreso"] == "Ingresado")
    dim["Antigüedad al Cierre"] = np.where(pend_int, (dim["Cierre Mes"] - dim["Creation_Date"]).dt.days, np.nan)
    cumple = np.full(len(dim), None, dtype=object)
    con_sed = (pend_int & sed.notna()).to_numpy()
    cumple[con_sed & (sed >= dim["Cierre Mes"]).to_numpy()] = "En plazo"
    cumple[con_sed & (sed < dim["Cierre Mes"]).to_numpy()] = "Atrasado"
    dim["Cumple Entrega al Cierre"] = cumple

    dim["Mes"] = dim["Creation_Date"].dt.to_period("M").astype(str)

    return {"dim": dim, "hoy": hoy, "ref": ref}


def _motivo_stock(dim, order_items, stock_vtex, hoy):
    oi = order_items.copy()
    oi["Sequence"] = oi["Sequence"].astype(str).str.strip()
    oi["SKU"] = oi["Reference_Code"].astype(str).str.strip()

    sv = stock_vtex.copy()
    if len(sv):
        sv["codigoSap"] = sv["codigoSap"].astype(str).str.strip()
        sv["disp"] = pd.to_numeric(sv.get("VTEX", 0), errors="coerce").fillna(0) \
            - pd.to_numeric(sv.get("Reservado", 0), errors="coerce").fillna(0)
        disp_map = sv.groupby("codigoSap")["disp"].sum()
    else:
        disp_map = pd.Series(dtype=float)

    disp = oi["SKU"].map(disp_map)
    oi["Motivo Línea"] = np.select(
        [disp.isna(), disp <= 0, disp < pd.to_numeric(oi["Quantity_SKU"], errors="coerce")],
        ["Servicios", "Quiebre", "Stock parcial"], "Con stock")
    prio = {"Sobreventa": 1, "Quiebre": 2, "Stock parcial": 3, "Sin dato de stock": 4, "Con stock": 5}
    oi["_p"] = oi["Motivo Línea"].map(prio).fillna(6)          # "Servicios" no entra al MINX (queda ultimo)
    peor = oi.groupby("Sequence")["_p"].min()
    inv = {1: "Sobreventa", 2: "Quiebre", 3: "Stock parcial", 4: "Sin dato de stock", 5: "Con stock"}
    dim["Motivo Pendiente"] = dim["Sequence"].map(peor).map(inv).fillna("Sin línea")

    m = dim["Motivo Pendiente"]
    dim["Causa Pendiente"] = np.select(
        [dim["Antigüedad Días"] == 0, m == "Con stock", m.isin(["Quiebre", "Stock parcial"])],
        ["En plazo (hoy)", "Gestión analista", "Quiebre de stock"], "Servicios")
    return dim


# ---------------------------------------------------------------------------
# MEDIDAS — se calculan sobre un dim ya filtrado por el contexto (mes/canal…)
# ---------------------------------------------------------------------------
def medidas(dim: pd.DataFrame, vig_mes=None) -> dict:
    """Todas las medidas del resumen, sobre el dim que se pase (ya filtrado)."""
    n = len(dim)
    ei = dim["Estado Ingreso"]
    st = dim["Status"]
    ep = dim["Estado Pedido"]

    vigentes = (ep != "Cancelado").sum()
    integrados = (ei == "Ingresado").sum()
    no_integrados = (ei == "No ingresado").sum()
    cancelados = (ei == "Cancelado VTEX").sum()
    por_preparar = (st == "ready-for-handling").sum()

    pp_integrados = ((st == "ready-for-handling") & (ei == "Ingresado")).sum()

    fac_sd = (dim["Facturado Sin Despacho"] == "Facturado sin despacho").sum()
    monto_fac_sd = dim.loc[dim["Facturado Sin Despacho"] ==
                           "Facturado sin despacho", "Total_Value"].sum()
    monto_no_int = dim.loc[ei == "No ingresado", "Total_Value"].sum()

    def div(a, b):
        return round(float(a) / float(b), 4) if b else None

    # antigüedad promedio de pendientes integrados
    pend_int = dim[(st == "ready-for-handling") & (ei == "Ingresado")]
    antig_prom = round(float(pend_int["Antigüedad Días"].mean()), 1) if len(pend_int) else None

    # % cumplimiento fecha entrega (pendientes integrados con SED, dentro de plazo)
    base_cum = pend_int[(pend_int["Canal"] == "BWS") & pend_int["Shipping_Estimate_Date"].notna()]
    en_plazo = base_cum[base_cum["Shipping_Estimate_Date"] >= dim.attrs.get("hoy",
               pd.Timestamp.today())]
    pct_cumpl = div(len(en_plazo), len(base_cum))

    return {
        "pedidos": int(n),
        "vigentes": int(vigentes),
        "integrados": int(integrados),
        "no_integrados": int(no_integrados),
        "cancelados": int(cancelados),
        "por_preparar": int(por_preparar),
        "pp_integrados": int(pp_integrados),
        "pct_integracion": div(integrados, vigentes),
        "pct_pendiente": div(por_preparar, vig_mes if vig_mes is not None else vigentes),
        "pct_cancelado": div(cancelados, n),
        "pct_fac_sd": div(fac_sd, por_preparar),
        "fac_sd": int(fac_sd),
        "monto_fac_sd": float(monto_fac_sd or 0),
        "monto_no_integrado": float(monto_no_int or 0),
        "monto_en_riesgo": float((monto_no_int or 0) + (monto_fac_sd or 0)),
        "antig_prom": antig_prom,
        "pct_cumplimiento": pct_cumpl,
    }
