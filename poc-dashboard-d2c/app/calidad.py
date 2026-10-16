"""Controles de calidad de datos del pipeline (exactitud, completitud, consistencia, actualizacion, validez, unicidad, integridad).

Se ejecutan sobre las tablas crudas ANTES de publicarlas o construir el modelo. Cada control entrega ok | alerta | falla:
una `falla` rechaza la publicacion (hay que corregir o dejar una excepcion escrita); una `alerta` se registra y se muestra.
"""
from __future__ import annotations

import pandas as pd

STATUS_VALIDOS = {"invoiced", "canceled", "ready-for-handling"}
CLAVES = ("Order", "Sequence", "Creation_Date", "Status", "Total_Value")


def _r(id_, dim, regla, estado, detalle, valor=None) -> dict:
    return {"id": id_, "dimension": dim, "regla": regla, "estado": estado, "detalle": detalle, "valor": valor}


def _pct(a, b) -> float:
    return round(100 * a / b, 2) if b else 0.0


def evaluar(orders: pd.DataFrame, items: pd.DataFrame, sap: pd.DataFrame, fact: pd.DataFrame, stock: pd.DataFrame,
            hoy: pd.Timestamp, fecha_validada: str | None = None) -> dict:
    """-> {"controles": [...], "ok": n, "alertas": n, "fallas": n, "puntaje": 0-100}. Nunca lanza por datos raros."""
    c: list[dict] = []
    n = len(orders)
    # --- volumen minimo
    c.append(_r("Q01", "Completitud", "Hay pedidos cargados", "ok" if n else "falla", f"{n} pedidos", n))
    if n:
        # --- unicidad
        dup = int(orders["Sequence"].duplicated().sum())
        c.append(_r("Q02", "Unicidad", "Sequence no se repite", "ok" if not dup else "falla", f"{dup} Sequence repetidos", dup))
        # --- completitud de campos clave
        for col in CLAVES:
            if col in orders:
                nulos = int(orders[col].isna().sum())
                est = "ok" if nulos == 0 else ("alerta" if _pct(nulos, n) < 1 else "falla")
                c.append(_r("Q03", "Completitud", f"{col} sin vacios", est, f"{nulos} vacios ({_pct(nulos, n)}%)", nulos))
        # --- validez: status conocidos
        raros = orders.loc[~orders["Status"].isin(STATUS_VALIDOS), "Status"].astype(str).unique()[:5]
        c.append(_r("Q04", "Validez", "Status dentro de los valores esperados", "ok" if not len(raros) else "falla",
                    "todos validos" if not len(raros) else "valores inesperados: " + ", ".join(raros)))
        # --- exactitud: montos
        tv = pd.to_numeric(orders["Total_Value"], errors="coerce")
        neg = int((tv < 0).sum())
        c.append(_r("Q05", "Exactitud", "Total_Value no negativo", "ok" if not neg else "falla", f"{neg} montos negativos", neg))
        med = float(tv[tv > 0].median()) if (tv > 0).any() else 0
        extremos = int((tv > med * 100).sum()) if med else 0
        c.append(_r("Q06", "Exactitud", "Sin montos extremos (>100 veces la mediana)", "ok" if not extremos else "alerta",
                    f"{extremos} pedidos con monto extremo (mediana {med:,.0f})".replace(",", "."), extremos))
        # --- validez: fechas
        f = pd.to_datetime(orders["Creation_Date"], errors="coerce")
        futuras = int((f > hoy + pd.Timedelta(days=1)).sum())
        c.append(_r("Q07", "Validez", "Sin fechas de creacion en el futuro", "ok" if not futuras else "falla", f"{futuras} pedidos con fecha futura", futuras))
        if fecha_validada:
            ant = int((f < pd.Timestamp(fecha_validada) - pd.Timedelta(days=1)).sum())
            c.append(_r("Q08", "Validez", "Sin pedidos anteriores a la fecha validada", "ok" if not ant else "alerta", f"{ant} pedidos anteriores", ant))
        # --- actualizacion
        ult = f.max()
        horas = (hoy - ult).total_seconds() / 3600 if pd.notna(ult) else None
        est = "falla" if horas is None else ("ok" if horas <= 36 else ("alerta" if horas <= 96 else "falla"))
        c.append(_r("Q09", "Actualización", "El ultimo pedido es reciente", est,
                    "sin fechas" if horas is None else f"el ultimo pedido tiene {horas:.0f} h de antiguedad", None if horas is None else round(horas, 1)))
        # --- consistencia pedidos vs lineas
        sin_linea = int((orders.get("Lineas", pd.Series(1, index=orders.index)) == 0).sum())
        c.append(_r("Q10", "Consistencia", "Pedidos con al menos una linea", "ok" if _pct(sin_linea, n) < 1 else "alerta",
                    f"{sin_linea} pedidos sin lineas ({_pct(sin_linea, n)}%)", sin_linea))
        if len(items) and "Sequence" in items:
            huerf = int((~items["Sequence"].isin(orders["Sequence"])).sum())
            c.append(_r("Q11", "Integridad", "Cada linea pertenece a un pedido cargado", "ok" if not huerf else "falla", f"{huerf} lineas huérfanas", huerf))
            if "Unidades" in orders and "Quantity_SKU" in items:
                a, b = float(orders["Unidades"].sum()), float(pd.to_numeric(items["Quantity_SKU"], errors="coerce").sum())
                dif = abs(a - b) / max(a, 1)
                c.append(_r("Q12", "Consistencia", "Unidades de pedidos = unidades de lineas (conciliacion)", "ok" if dif < .005 else ("alerta" if dif < .05 else "falla"),
                            f"pedidos {a:,.0f} vs lineas {b:,.0f} ({dif * 100:.2f}% de diferencia)".replace(",", "."), round(dif * 100, 2)))
        # --- deriva de volumen y ticket (ultimos 7 dias contra los 28 anteriores)
        dia = f.dt.normalize()
        rec, base = orders[dia > hoy - pd.Timedelta(days=7)], orders[(dia <= hoy - pd.Timedelta(days=7)) & (dia > hoy - pd.Timedelta(days=35))]
        if len(base) >= 50:
            v7, v28 = len(rec) / 7, len(base) / 28
            var = v7 / v28 - 1 if v28 else 0
            c.append(_r("Q13", "Consistencia", "Volumen diario estable (7 d contra 28 d)", "ok" if abs(var) < .5 else "alerta",
                        f"{v7:.0f}/día contra {v28:.0f}/día ({var * 100:+.0f}%)", round(var * 100, 1)))
            t7, t28 = float(pd.to_numeric(rec["Total_Value"], errors="coerce").mean()), float(pd.to_numeric(base["Total_Value"], errors="coerce").mean())
            vt = t7 / t28 - 1 if t28 else 0
            c.append(_r("Q14", "Exactitud", "Ticket medio estable (7 d contra 28 d)", "ok" if abs(vt) < .3 else "alerta",
                        f"{t7:,.0f} contra {t28:,.0f} ({vt * 100:+.0f}%)".replace(",", "."), round(vt * 100, 1)))
    # --- SAP y facturacion
    if len(sap):
        dup_sap = int(sap.duplicated().sum())
        c.append(_r("Q15", "Unicidad", "Ingresos SAP sin filas duplicadas", "ok" if not dup_sap else "alerta", f"{dup_sap} filas repetidas", dup_sap))
        if n:
            union = len(set(sap["OrdenCompra"].astype(str).str.strip()) & set(orders["Sequence"].astype(str).str.strip()))
            c.append(_r("Q16", "Consistencia", "Los ingresos SAP calzan con pedidos VTEX (OrdenCompra = Sequence)", "ok" if union else "alerta",
                        f"{union} pedidos en comun", union))
    else:
        c.append(_r("Q15", "Completitud", "Hay ingresos SAP", "alerta", "la tabla de ingresos SAP vino vacia", 0))
    # --- stock
    if len(stock):
        d = int(stock["codigoSap"].duplicated().sum())
        c.append(_r("Q17", "Unicidad", "Un registro de stock por codigo SAP", "ok" if not d else "alerta", f"{d} codigos repetidos (se suman)", d))
        v, rsv = pd.to_numeric(stock["VTEX"], errors="coerce"), pd.to_numeric(stock["Reservado"], errors="coerce")
        neg = int(((v < 0) | (rsv < 0)).sum())
        c.append(_r("Q18", "Exactitud", "Stock y reservado no negativos", "ok" if not neg else "alerta", f"{neg} filas con valores negativos", neg))
    else:
        c.append(_r("Q17", "Completitud", "Hay datos de stock", "alerta", "la tabla de stock vino vacia", 0))
    ok, al, fa = (sum(x["estado"] == e for x in c) for e in ("ok", "alerta", "falla"))
    return {"controles": c, "ok": ok, "alertas": al, "fallas": fa, "puntaje": round(100 * (ok + .5 * al) / max(len(c), 1))}
