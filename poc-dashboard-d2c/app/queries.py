"""Consultas SQL portadas EXACTAS del dashboard Power BI (POC_Dashboard_D2C.pbix).

Cada función devuelve un DataFrame con las mismas columnas que la tabla del modelo.
El parámetro de fecha validada se inserta como literal seguro (formato ISO fijo).
"""
from __future__ import annotations

import pandas as pd

from .config import settings
from .db import leer_sap, leer_vtex

CANALES_IN = "(6,1,2,4,5,3,9,8,10,12,13,14,15,17,19)"


def _fv() -> str:
    """Fecha validada saneada a 'YYYY-MM-DD' (solo dígitos y guiones)."""
    v = "".join(c for c in settings.fecha_validada if c.isdigit() or c == "-")
    return v or "2026-07-14"


# ---------------------------------------------------------------------------
# Orders (VTEX) — cabecera con SLA/warehouse a nivel pedido y huso corregido
# ---------------------------------------------------------------------------
def q_orders() -> pd.DataFrame:
    fv = _fv()
    sql = f"""
    WITH O AS (
        SELECT [Order],[Sequence],[Status],[Total_Value],[SalesChannel],
            CAST(CAST([Creation_Date] AS datetime2) AT TIME ZONE 'UTC'
                 AT TIME ZONE 'Pacific SA Standard Time' AS datetime2) AS Creation_CL,
            CAST(CAST([Record_Date] AS datetime2) AT TIME ZONE 'UTC'
                 AT TIME ZONE 'Pacific SA Standard Time' AS datetime2) AS Record_CL
        FROM Orders
        WHERE [Country]='CH'
          AND [Creation_Date] >= DATEADD(day,-1,CAST('{fv}' AS DATE))   -- pre-filtro (usa indice, evita convertir todo el historial)
    )
    SELECT o.[Order], o.[Sequence],
        CAST(o.Creation_CL AS DATE) AS Creation_Date,
        CAST(o.Record_CL   AS DATE) AS Record_Date,
        o.Creation_CL AS Creation_DateTime,
        o.[Status], o.[Total_Value], o.[SalesChannel],
        CASE
            WHEN o.[SalesChannel]=6  THEN 'Electrolux' WHEN o.[SalesChannel]=1  THEN 'Fensa'
            WHEN o.[SalesChannel]=2  THEN 'Shopclub'   WHEN o.[SalesChannel]=4  THEN 'Empresas'
            WHEN o.[SalesChannel]=5  THEN 'Mademsa'    WHEN o.[SalesChannel]=3  THEN 'Ripley'
            WHEN o.[SalesChannel]=9  THEN 'Colaboradores' WHEN o.[SalesChannel]=8 THEN 'MELI'
            WHEN o.[SalesChannel]=10 THEN 'Totem'      WHEN o.[SalesChannel]=12 THEN 'Paris'
            WHEN o.[SalesChannel]=13 THEN 'Rappi'      WHEN o.[SalesChannel]=14 THEN 'Reposición'
            WHEN o.[SalesChannel]=15 THEN 'Falabella'  WHEN o.[SalesChannel]=17 THEN 'Walmart'
            WHEN o.[SalesChannel]=19 THEN 'Hites'      ELSE 'Otro'
        END AS SalesChannelName,
        CASE WHEN sla.[Sequence] IS NULL THEN 'Sin línea'
             WHEN sla.nSLA>1 THEN 'Multi-SLA' ELSE sla.SLA_Type END AS SLA_Type,
        CASE WHEN sla.[Sequence] IS NULL THEN 'Sin línea'
             WHEN sla.nWh>1 THEN 'Multi-CD' ELSE sla.warehouse END AS warehouse,
        ISNULL(sla.Unidades,0) AS Unidades, ISNULL(sla.Lineas,0) AS Lineas,
        sla.Shipping_Estimate_Date
    FROM O o
    LEFT JOIN (
        SELECT oi.[Sequence],
            COUNT(DISTINCT CASE
                WHEN oi.[SLA_Type]='MELI HB' THEN 'MELI Heavy and Bulky'
                WHEN oi.[SLA_Type]='MELI HB Blue' THEN 'MELI Bluexpress'
                WHEN oi.[SLA_Type]='Despacho Mercado Libre (SDA)' THEN 'MELI Colecta'
                WHEN oi.[SLA_Type]='vtex:fob_167f2ea' THEN 'Falabella MKP'
                ELSE oi.[SLA_Type] END) AS nSLA,
            MIN(CASE
                WHEN oi.[SLA_Type]='MELI HB' THEN 'MELI Heavy and Bulky'
                WHEN oi.[SLA_Type]='MELI HB Blue' THEN 'MELI Bluexpress'
                WHEN oi.[SLA_Type]='Despacho Mercado Libre (SDA)' THEN 'MELI Colecta'
                WHEN oi.[SLA_Type]='vtex:fob_167f2ea' THEN 'Falabella MKP'
                ELSE oi.[SLA_Type] END) AS SLA_Type,
            COUNT(DISTINCT CASE WHEN oi.[warehouse]='1_1' THEN 'EC01'
                WHEN oi.[warehouse]='1533f30' THEN 'POS_Fechado' ELSE oi.[warehouse] END) AS nWh,
            MIN(CASE WHEN oi.[warehouse]='1_1' THEN 'EC01'
                WHEN oi.[warehouse]='1533f30' THEN 'POS_Fechado' ELSE oi.[warehouse] END) AS warehouse,
            SUM(oi.[Quantity_SKU]) AS Unidades, COUNT(*) AS Lineas,
            MIN(CAST(oi.[Shipping_Estimate_Date] AS DATE)) AS Shipping_Estimate_Date
        FROM OrderItems oi
        INNER JOIN O o2 ON o2.[Sequence]=oi.[Sequence]
        WHERE oi.[Country]='CH' AND CAST(o2.Creation_CL AS DATE) >= CAST('{fv}' AS DATE)
        GROUP BY oi.[Sequence]
    ) sla ON sla.[Sequence]=o.[Sequence]
    WHERE o.[Status] IN ('invoiced','canceled','ready-for-handling')
      AND CAST(o.Creation_CL AS DATE) >= CAST('{fv}' AS DATE)
      AND o.[SalesChannel] IN {CANALES_IN}
    """
    return leer_vtex(sql)


def q_order_items() -> pd.DataFrame:
    fv = _fv()
    sql = f"""
    WITH O AS (
        SELECT [Sequence],[Status],[SalesChannel],
            CAST(CAST([Creation_Date] AS datetime2) AT TIME ZONE 'UTC'
                 AT TIME ZONE 'Pacific SA Standard Time' AS datetime2) AS Creation_CL
        FROM Orders
        WHERE [Country]='CH'
          AND [Creation_Date] >= DATEADD(day,-1,CAST('{fv}' AS DATE))   -- pre-filtro
    )
    -- solo las 3 columnas que usa el modelo (motivo de stock por linea)
    SELECT oi.[Sequence],oi.[Quantity_SKU],oi.[Reference_Code]
    FROM OrderItems oi
    INNER JOIN O o ON o.[Sequence]=oi.[Sequence]
    WHERE oi.[Country]='CH' AND o.[Status] IN ('invoiced','canceled','ready-for-handling')
      AND CAST(o.Creation_CL AS DATE) >= CAST('{fv}' AS DATE)
      AND o.[SalesChannel] IN {CANALES_IN}
    """
    return leer_vtex(sql)


def q_sap_ingresos() -> pd.DataFrame:
    fv = _fv()
    sql = f"""
    SELECT DISTINCT CAST(p.Fecha AS DATE) AS Fecha_Pedido, p.OrdenCompra, p.Pedido
    FROM od_pedidos_ingresados p
    WHERE p.Fecha >= DATEADD(day,-1,CAST('{fv}' AS DATE))
    """
    return leer_sap(sql)


def q_facturacion() -> pd.DataFrame:
    sql = """
    SELECT fa.ordenCompra, MIN(DATEFROMPARTS(fa.año,fa.mes,fa.dia)) AS Fecha
    FROM dp_facturacion fa
    LEFT JOIN bi_canal_sellin ca ON ca.idCanal=fa.canal
    WHERE fa.año>2025 AND ca.nombreCanal IN ('D2C OnLine','D2C Offline')
    GROUP BY fa.ordenCompra
    """
    return leer_sap(sql)


def q_stock_vtex() -> pd.DataFrame:
    """Stock VTEX (disponible = VTEX - Reservado), del ODS."""
    sql = "SELECT codigoSap, VTEX, Reservado FROM bi_stock_vtex"
    try:
        return leer_sap(sql)
    except Exception:
        return pd.DataFrame(columns=["codigoSap", "VTEX", "Reservado"])


def q_hoy_cl() -> pd.Timestamp:
    """Hoy en hora Chile, desde el mismo Azure (parámetro Hoy_CL del .pbix)."""
    df = leer_vtex("SELECT CAST(SYSDATETIMEOFFSET() AT TIME ZONE "
                   "'Pacific SA Standard Time' AS DATE) AS Hoy_CL")
    return pd.Timestamp(df["Hoy_CL"].iloc[0])


def q_firma() -> str:
    """Huella LIVIANA del estado de los datos: solo conteos y totales, sin traer filas.

    Si cambia (pedido nuevo, cambio de estado, ingreso a SAP, factura), el servidor recarga todo.
    Usa exactamente las mismas tablas y filtros que las consultas principales.
    """
    fv = _fv()
    v = leer_vtex(f"""
        SELECT COUNT(*) AS n, MAX([Creation_Date]) AS ult,
            SUM(CASE WHEN [Status]='ready-for-handling' THEN 1 ELSE 0 END) AS rfh,
            SUM(CASE WHEN [Status]='invoiced' THEN 1 ELSE 0 END) AS inv,
            SUM(CASE WHEN [Status]='canceled' THEN 1 ELSE 0 END) AS can,
            SUM(CAST([Total_Value] AS DECIMAL(38,2))) AS monto
        FROM Orders
        WHERE [Country]='CH' AND [Status] IN ('invoiced','canceled','ready-for-handling')
          AND [SalesChannel] IN {CANALES_IN}
          AND [Creation_Date] >= DATEADD(day,-1,CAST('{fv}' AS DATE))""")
    s = leer_sap(f"""
        SELECT COUNT(*) AS n, MAX(Fecha) AS ult, SUM(CAST(monto AS DECIMAL(38,2))) AS m
        FROM od_pedidos_ingresados
        WHERE Fecha >= DATEADD(day,-1,CAST('{fv}' AS DATE))""")
    f = leer_sap("""
        SELECT COUNT(*) AS n, SUM(CAST(fa.monto AS DECIMAL(38,2))) AS m
        FROM dp_facturacion fa
        LEFT JOIN bi_canal_sellin ca ON ca.idCanal=fa.canal
        WHERE fa.año>2025 AND ca.nombreCanal IN ('D2C OnLine','D2C Offline')""")
    return "|".join(str(x) for x in (*v.iloc[0].tolist(), *s.iloc[0].tolist(), *f.iloc[0].tolist()))
