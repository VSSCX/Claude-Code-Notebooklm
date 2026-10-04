"""Datos de ejemplo para probar la plataforma sin conexion a SQL Server.

Se activa con DEMO=1 en el .env. Genera un universo sintetico parecido al real
(canales, estados, desfases, alertas). Es DETERMINISTA: cada carga entrega los mismos
datos, salvo los pedidos que se agregan con "simular pedido" (para ver la actualizacion
en vivo funcionando).
"""
from __future__ import annotations

import random
import threading
from datetime import date, datetime, timedelta

import pandas as pd

CANALES = ["MELI", "Mademsa", "Falabella", "Electrolux", "Totem", "Fensa",
           "Walmart", "Ripley", "Paris", "Hites", "Colaboradores"]
SLAS = ["MELI Heavy and Bulky", "Convencional", "Falabella MKP", "MELI Bluexpress",
        "Recibe Mañana", "Recibe Hoy", "Despacho Programado RM"]
WHS = ["EC01", "POS_Fechado", "CD45", "CD52"]
HOY = date(2026, 8, 11)

_LOCK = threading.Lock()
_EXTRAS: list = []          # pedidos simulados (orden, linea, stock)


def firma_demo() -> int:
    """Cambia cuando se simula un pedido (equivale a la consulta liviana de SQL)."""
    return len(_EXTRAS)


def agregar_pedido() -> dict:
    """Simula la llegada de un pedido nuevo a VTEX (aun sin ingresar a SAP)."""
    with _LOCK:
        if len(_EXTRAS) >= 500:          # tope: el demo no debe crecer sin limite
            return {"sequence": str(9000000 + len(_EXTRAS)), "canal": "-", "hora": "-", "tope": True}
        n = len(_EXTRAS) + 1
        r = random.Random(1000 + n)
        ahora = datetime.now()
        creado = datetime(HOY.year, HOY.month, HOY.day, ahora.hour, ahora.minute, ahora.second)
        seq = str(9000000 + n)
        canal = r.choice(CANALES)
        sla = r.choice(SLAS)
        unid = r.randint(1, 4)
        sku = f"9{r.randint(10000000, 99999999)}"
        monto = r.randint(60000, 700000)
        orden = {"Order": f"MEL-{seq}", "Sequence": seq, "Creation_Date": HOY, "Record_Date": HOY,
                 "Creation_DateTime": creado, "Status": "ready-for-handling", "Total_Value": monto,
                 "SalesChannel": 8, "SalesChannelName": canal, "SLA_Type": sla, "warehouse": "EC01",
                 "Unidades": unid, "Lineas": 1, "Shipping_Estimate_Date": HOY + timedelta(days=r.choice([0, 1, 2]))}
        linea = {"Order": orden["Order"], "Sequence": seq, "Quantity_SKU": unid, "Reference_Code": sku,
                 "SKU_Name": "Producto demo", "SLA_Type": sla,
                 "Shipping_Estimate_Date": orden["Shipping_Estimate_Date"], "warehouse": "EC01"}
        stock = {"codigoSap": sku, "VTEX": r.randint(5, 40), "Reservado": r.randint(0, 3)}
        _EXTRAS.append((orden, linea, stock))
        return {"sequence": seq, "canal": canal, "hora": creado.strftime("%H:%M:%S")}


def datos_demo():
    R = random.Random(42)
    ini = date(2026, 7, 14)
    dias = (HOY - ini).days
    orders, items, sap, fact, stock = [], [], [], [], []
    seq = 3500000
    for d in range(dias + 1):
        f = ini + timedelta(days=d)
        n = R.randint(300, 460)
        caido = f == date(2026, 7, 18)           # ese dia la interfaz a SAP se cae
        reciente = (HOY - f).days <= 1
        for _ in range(n):
            seq += 1
            s = str(seq)
            canal = R.choices(CANALES, weights=[30, 20, 12, 8, 7, 6, 4, 4, 3, 2, 2])[0]
            sla = R.choice(SLAS)
            wh = R.choices(WHS, weights=[85, 5, 5, 5])[0]
            monto = R.randint(30000, 900000)
            unid = R.randint(1, 6)
            if R.random() < 0.02:
                status = "canceled"
            elif reciente and R.random() < 0.4:
                status = "ready-for-handling"
            else:
                status = R.choices(["invoiced", "ready-for-handling"], weights=[90, 10])[0]
            sed = f + timedelta(days=R.choice([-1, 0, 0, 1, 2, 3, 5]))
            hora = datetime(f.year, f.month, f.day) + timedelta(seconds=R.randint(0, 86399))
            orders.append({
                "Order": f"MEL-{seq}", "Sequence": s, "Creation_Date": f, "Record_Date": f,
                "Creation_DateTime": hora, "Status": status, "Total_Value": monto, "SalesChannel": 8,
                "SalesChannelName": canal, "SLA_Type": sla, "warehouse": wh, "Unidades": unid,
                "Lineas": 1, "Shipping_Estimate_Date": sed})
            sku = f"9{R.randint(10000000, 99999999)}"
            items.append({"Order": f"MEL-{seq}", "Sequence": s, "Quantity_SKU": unid,
                          "Reference_Code": sku, "SKU_Name": "Producto demo", "SLA_Type": sla,
                          "Shipping_Estimate_Date": sed, "warehouse": wh})
            stock.append({"codigoSap": sku, "VTEX": R.randint(0, 50), "Reservado": R.randint(0, 10)})
            if not caido and not reciente and R.random() < 0.9:
                sap.append({"Fecha_Pedido": f, "Canal": "3._  D2C ONLINE", "OrdenCompra": s,
                            "clasePedido": "ZOR", "Pedido": str(4000000 + seq), "codigoSAP": sku,
                            "Posicion": 10, "Monto_Pedido": monto, "QtyPedido": unid})
            if status == "ready-for-handling" and R.random() < 0.03:
                fact.append({"Fecha": f + timedelta(days=R.randint(0, 4)), "clasePedido": "ZOR",
                             "nombreCanal": "D2C OnLine", "codigoSap": sku, "pedido": str(5000000 + seq),
                             "ordenCompra": s, "qty": unid, "monto": monto})
    with _LOCK:
        for o, l, st in _EXTRAS:
            orders.append(o); items.append(l); stock.append(st)
    return (pd.DataFrame(orders), pd.DataFrame(items), pd.DataFrame(sap),
            pd.DataFrame(fact), pd.DataFrame(stock), pd.Timestamp(HOY))
