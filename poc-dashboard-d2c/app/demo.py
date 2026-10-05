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
WHS = ["EC01", "POST_Fechado", "CD45", "CD52"]
HOY = date(2026, 8, 11)

# Catalogo de ejemplo: (codigo SAP, descripcion, precio unitario CLP, peso de venta, stock VTEX)
CATALOGO = [
    ("910016501", "Refrigerador Frío Directo MED 165B 165 L Blanco", 169990, 14, 38),
    ("910016502", "Refrigerador Frío Directo MED 165B 165 L Inox", 189990, 6, 0),
    ("910028001", "Refrigerador Top Freezer MED 280A 280 L", 329990, 9, 22),
    ("910041001", "Refrigerador No Frost Side by Side SBS 540 L", 899990, 3, 7),
    ("910008001", "Frigobar MED 80F 80 L", 119990, 6, 40),
    ("910014001", "Congelador Horizontal CH 140 L", 259990, 3, 12),
    ("920008501", "Lavadora Carga Frontal LF 8,5 kg", 349990, 10, 25),
    ("920010001", "Lavadora Carga Superior LS 10 kg", 289990, 10, 30),
    ("920012001", "Lavadora Secadora LS 12/7 kg", 599990, 3, 6),
    ("920009001", "Secadora de Ropa a Gas SG 9 kg", 399990, 3, 0),
    ("930060001", "Cocina a Gas 4 Quemadores CG 60 Inox", 249990, 8, 18),
    ("930090001", "Cocina Empotrable 5 Quemadores CE 90", 459990, 3, 9),
    ("930070001", "Horno Eléctrico Empotrable HE 70 L", 319990, 4, 14),
    ("930036001", "Encimera a Gas 3 Quemadores EG 36", 149990, 4, 20),
    ("940060001", "Campana Extractora Decorativa CD 60", 129990, 5, 33),
    ("940090001", "Campana Extractora de Pared CP 90", 189990, 3, 11),
    ("950025001", "Microondas Digital MW 25 L", 99990, 7, 45),
    ("960001001", "Aspiradora Sin Bolsa AS 1800 W", 89990, 5, 28),
    ("970012001", "Lavavajillas Libre Instalación LV 12 Servicios", 549990, 2, 5),
    ("980050001", "Purificador de Aire PA 50 m2", 159990, 2, 16),
]
_PESOS = [c[3] for c in CATALOGO]
STOCK_DEMO = {c[0]: c[4] for c in CATALOGO}


def _lineas(R, seq, orden, sla, sed, wh):
    """1 a 3 lineas por pedido, sacadas del catalogo. Devuelve (lineas, unidades, monto)."""
    n = R.choices([1, 2, 3], weights=[70, 22, 8])[0]
    cods = R.choices(CATALOGO, weights=_PESOS, k=n)
    vistos, out = set(), []
    for cod, desc, precio, _, _ in cods:
        if cod in vistos:
            continue
        vistos.add(cod)
        out.append({"Order": orden, "Sequence": seq, "Quantity_SKU": R.choices([1, 2, 3, 4], weights=[72, 18, 7, 3])[0],
                    "Reference_Code": cod, "SKU_Name": desc, "Selling_Price": precio, "SLA_Type": sla,
                    "Shipping_Estimate_Date": sed, "warehouse": wh})
    return out, sum(l["Quantity_SKU"] for l in out), sum(l["Quantity_SKU"] * l["Selling_Price"] for l in out)


_ULTIMAS_LINEAS: list = []   # lineas de la ultima carga (para el detalle de un pedido y el asistente)


def lineas_demo():
    with _LOCK:
        return pd.DataFrame(_ULTIMAS_LINEAS)

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
        wh = "EC01"
        sed = HOY + timedelta(days=r.choice([0, 1, 2]))
        orden_id = f"MEL-{seq}"
        lineas, unid, monto = _lineas(r, seq, orden_id, sla, sed, wh)
        orden = {"Order": orden_id, "Sequence": seq, "Creation_Date": HOY, "Record_Date": HOY,
                 "Creation_DateTime": creado, "Status": "ready-for-handling", "Total_Value": monto,
                 "SalesChannel": 8, "SalesChannelName": canal, "SLA_Type": sla, "warehouse": wh,
                 "Unidades": unid, "Lineas": len(lineas), "Shipping_Estimate_Date": sed}
        stock = []
        _EXTRAS.append((orden, lineas, stock))
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
            if R.random() < 0.02:
                status = "canceled"
            elif reciente and R.random() < 0.4:
                status = "ready-for-handling"
            else:
                status = R.choices(["invoiced", "ready-for-handling"], weights=[90, 10])[0]
            sed = f + timedelta(days=R.choice([-1, 0, 0, 1, 2, 3, 5]))
            hora = datetime(f.year, f.month, f.day) + timedelta(seconds=R.randint(0, 86399))
            lineas, unid, monto = _lineas(R, s, f"MEL-{seq}", sla, sed, wh)
            orders.append({
                "Order": f"MEL-{seq}", "Sequence": s, "Creation_Date": f, "Record_Date": f,
                "Creation_DateTime": hora, "Status": status, "Total_Value": monto, "SalesChannel": 8,
                "SalesChannelName": canal, "SLA_Type": sla, "warehouse": wh, "Unidades": unid,
                "Lineas": len(lineas), "Shipping_Estimate_Date": sed})
            items.extend(lineas)
            ingresa = not caido and not reciente and R.random() < 0.9      # el pedido entra a SAP completo (todas sus lineas)
            for k, l in enumerate(lineas if ingresa else []):
                sap.append({"Fecha_Pedido": f, "Canal": "3._  D2C ONLINE", "OrdenCompra": s,
                            "clasePedido": "ZOR", "Pedido": str(4000000 + seq), "codigoSAP": l["Reference_Code"],
                            "Posicion": 10 * (k + 1), "Monto_Pedido": l["Quantity_SKU"] * l["Selling_Price"],
                            "QtyPedido": l["Quantity_SKU"]})
            if status == "ready-for-handling" and R.random() < 0.03:
                fact.append({"Fecha": f + timedelta(days=R.randint(0, 4)), "clasePedido": "ZOR",
                             "nombreCanal": "D2C OnLine", "codigoSap": lineas[0]["Reference_Code"],
                             "pedido": str(5000000 + seq), "ordenCompra": s, "qty": unid, "monto": monto})
    stock = [{"codigoSap": c[0], "VTEX": c[4], "Reservado": 0} for c in CATALOGO]
    with _LOCK:
        for o, ls, _ in _EXTRAS:
            orders.append(o); items.extend(ls)
        _ULTIMAS_LINEAS[:] = items
    return (pd.DataFrame(orders), pd.DataFrame(items), pd.DataFrame(sap),
            pd.DataFrame(fact), pd.DataFrame(stock), pd.Timestamp(HOY))
