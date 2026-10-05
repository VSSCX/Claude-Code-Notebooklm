# -*- coding: utf-8 -*-
"""Prueba del asistente de consultas con los datos de ejemplo. Uso:  python probar_asistente.py

Cada pregunta se compara contra una cifra calculada a mano con pandas (no con el codigo del asistente), asi se
comprueba que entiende la pregunta Y que la cifra es correcta. Sale con codigo 1 si algo falla.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

os.environ["DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from app import asistente, servicio  # noqa: E402

dim, hoy = servicio.base_pedidos()
_, _, lin, _ = servicio.lineas_todas()
L = lin.merge(dim[["Sequence", "Creation_Date", "Status", "warehouse", "SalesChannelName", "Total_Value", "Estado Ingreso"]], on="Sequence")
fallos = []


def p(q, previo=None):
    return asistente.responder(q, previo)


def prueba(nombre, ok, detalle=""):
    print(("  [OK]    " if ok else "  [FALLA] ") + nombre + (f"  ->  {detalle}" if not ok and detalle else ""))
    if not ok:
        fallos.append(nombre)


def cerca(a, b):
    return a is not None and abs(float(a) - float(b)) < .5


med = L[L["Descripcion"].str.contains("MED 165B")]
d7 = lambda df: df[(df["Creation_Date"] >= hoy - timedelta(days=6)) & (df["Creation_Date"] <= hoy) & (df["Status"] != "canceled")]  # noqa: E731

print("Productos y ventas")
r = p("cual es la venta de los ultimos 7 días del med165b")
prueba("venta 7 dias del MED165B (monto) reconoce 'med165b' como el refrigerador", r["ok"] and "MED 165B" in r["productos"][0]["descripcion"] and cerca(r["valor"], d7(med)["Monto"].sum()), str(r.get("valor")))
r = p("cuantas unidades del refrigerador med 165b cayeron hoy")
hh = med[(med["Creation_Date"] == hoy) & (med["Status"] != "canceled")]
prueba("unidades del MED 165B hoy", cerca(r["valor"], hh["Qty"].sum()))
r = p("unidades de la lavadora 8,5 kg ultimos 7 dias")
lav = L[L["Descripcion"].str.contains("8,5 kg")]
prueba("lavadora 8,5 kg (decimal con coma)", cerca(r["valor"], d7(lav)["Qty"].sum()))
r = p("ventas del refrigeradro med165b hoy")
prueba("corrige un error de tipeo (refrigeradro)", r["ok"] and any("refrigeradro" in n for n in r["notas"]))
r = p("unidades del refrigerador xyz999 hoy")
prueba("modelo inexistente: no responde con otro producto", r["ok"] is False and "No encontré" in r["texto"])
r = p("unidades del sku 910016501 hoy")
prueba("por codigo SAP", cerca(r["valor"], L[(L["SKU"] == "910016501") & (L["Creation_Date"] == hoy) & (L["Status"] != "canceled")]["Qty"].sum()))

print("Estados y status")
for q, filtro, nombre in [("cuantos pedidos se cancelaron en el ultimo mes", dim["Status"] == "canceled", "cancelados"),
                          ("cuantos pedidos facturados hoy", dim["Status"] == "invoiced", "facturados hoy"),
                          ("cuantos pedidos pendientes hay hoy", dim["Status"] == "ready-for-handling", "pendientes hoy")]:
    r = p(q)
    ini, fin = ((hoy - timedelta(days=29), hoy) if "ultimo mes" in q else (hoy, hoy))
    esperado = int((filtro & (dim["Creation_Date"] >= ini) & (dim["Creation_Date"] <= fin) & ((dim["Status"] != "canceled") | (nombre == "cancelados"))).sum())
    prueba(f"pedidos {nombre}", r["ok"] and cerca(r["valor"], esperado), f"{r.get('valor')} vs {esperado}")
r = p("cuantos pedidos sin integrar de falabella este mes")
e = dim[(dim["Estado Ingreso"] == "No ingresado") & (dim["SalesChannelName"] == "Falabella") & (dim["Creation_Date"] >= hoy.replace(day=1)) & (dim["Status"] != "canceled")]
prueba("no integrados de Falabella", cerca(r["valor"], len(e)))
r = p("pedidos pendientes con entrega vencida")
e = dim[(dim["Status"] == "ready-for-handling") & (dim["Shipping_Estimate_Date"] < hoy) & (dim["Creation_Date"] >= hoy.replace(day=1))]
prueba("pendientes con entrega vencida", cerca(r["valor"], len(e)), f"{r.get('valor')} vs {len(e)}")

print("POST Fechado")
r = p("cual es el status de post fechado hoy")
e = dim[(dim["warehouse"] == "POST_Fechado") & (dim["Creation_Date"] == hoy)].groupby("Status").size().to_dict()
got = {f[0].split(" ")[0]: f[1] for f in r["tabla"]["filas"]}
prueba("status de POST Fechado hoy (desglose)", r["tipo"] == "tabla" and sum(got.values()) == sum(e.values()), f"{got} vs {e}")
r = p("que me indique los pedidos post fechados de hoy, productos, qty y monto")
lp = L[(L["warehouse"] == "POST_Fechado") & (L["Creation_Date"] == hoy) & (L["Status"] != "canceled")]
nombres = [c["n"] for c in r["tabla"]["cols"]]
prueba("lista pedidos POST Fechado con productos, cantidad y monto", r["tipo"] == "lista" and {"Pedido", "Producto", "Cant.", "Monto"} <= set(nombres)
       and len(r["tabla"]["filas"]) == len(lp) and cerca(sum(f[3] for f in r["tabla"]["filas"]), lp["Monto"].sum()))
r2 = p("y ayer?", r["plan"])
prueba("seguimiento 'y ayer?' conserva POST Fechado y la lista", r2["tipo"] == "lista" and r2["plan"]["bodega"] == ["POST_Fechado"] and r2["plan"]["periodo"] == "ayer")

print("Desgloses, rankings y comparaciones")
r = p("top 3 clientes por monto este mes")
e = dim[(dim["Creation_Date"] >= hoy.replace(day=1)) & (dim["Status"] != "canceled")].groupby("SalesChannelName")["Total_Value"].sum().sort_values(ascending=False).head(3)
prueba("top 3 clientes por monto", [f[0] for f in r["tabla"]["filas"]] == list(e.index) and cerca(r["tabla"]["filas"][0][3], e.iloc[0]))
r = p("pedidos por dia ultimos 5 dias")
esp = dim[(dim["Creation_Date"] > hoy - timedelta(days=5)) & (dim["Status"] != "canceled")].groupby("Creation_Date").size()
prueba("pedidos por dia (5 filas, cronologico, con las cifras correctas)", [f[1] for f in r["tabla"]["filas"]] == list(esp.values) and [f[0] for f in r["tabla"]["filas"]] == [d.strftime("%d-%m-%Y") for d in esp.index])
r = p("compara las ventas de esta semana con la anterior")
prueba("comparacion con el periodo anterior", r["comparacion"] is not None and cerca(r["comparacion"]["delta"], r["valor"] - r["comparacion"]["anterior"]))
r = p("ticket promedio de meli este mes")
e = dim[(dim["SalesChannelName"] == "MELI") & (dim["Creation_Date"] >= hoy.replace(day=1)) & (dim["Status"] != "canceled")]
prueba("ticket promedio", cerca(r["valor"], e["Total_Value"].mean()))

print("Stock, pedido, ayuda e informacion")
r = p("hay stock del med165b")
prueba("stock del MED165B (2 variantes, una sin stock)", r["tipo"] == "stock" and len(r["tabla"]["filas"]) == 2 and "Sin stock" in r["texto"])
r = p("cuales productos estan sin stock")
prueba("productos sin stock", r["tipo"] == "stock" and r["valor"] >= 1)
r = p("pedido 3500002")
prueba("detalle de un pedido", r["tipo"] == "pedido" and r["lineas"])
sap = dim[dim["Pedido SAP"] != ""].iloc[0]["Pedido SAP"].split(" | ")[0]
prueba("buscar un pedido por su numero SAP", p(f"estado del pedido sap {sap}")["tipo"] == "pedido")
prueba("saludo y ayuda", p("hola").get("ayuda") and p("que puedes hacer").get("ayuda"))
prueba("hasta cuando hay datos", "pedidos cargados" in p("hasta cuando hay datos")["texto"])
prueba("pregunta que no entiende", p("blablabla")["ok"] is False)
prueba("pregunta vacia o muy larga no rompe", p("")["ok"] is False and p("x" * 5000)["ok"] is False)

print("Ventas por Clasif2 (maestra de productos)")
from app import items, ventas  # noqa: E402
from app.demo import CLASIF2  # noqa: E402

nc = dim[(dim["Creation_Date"] >= hoy.replace(day=1)) & (dim["Status"] != "canceled")]
lv = lin.merge(nc[["Sequence", "SalesChannelName"]], on="Sequence")
lv["C2"] = lv["SKU"].map(CLASIF2)
esp = lv.groupby("C2")["Monto"].sum().sort_values(ascending=False)
f_mes = {"alcance": "todos", "fecha_ini": hoy.replace(day=1).strftime("%Y-%m-%d"), "fecha_fin": hoy.strftime("%Y-%m-%d")}
v = ventas.ventas(f_mes)
prueba("ventas por Clasif2 coinciden con el calculo a mano", v["ok"] and [c["nombre"] for c in v["clasif"]] == list(esp.index) and cerca(v["total"], esp.sum()))
v2 = ventas.ventas({**f_mes, "cliente": ["MELI"]})
e2 = lv[lv["SalesChannelName"] == "MELI"].groupby("C2")["Monto"].sum()
prueba("respeta el filtro de cliente (clic en MELI)", cerca(v2["total"], e2.sum()) and v2["total"] < v["total"])
v3 = ventas.ventas(f_mes, "Lavadoras")
prueba("zoom: productos de una clasificacion", [p["producto"] for p in v3["productos"]] == list(lv[lv["C2"] == "Lavadoras"].groupby("Descripcion")["Monto"].sum().sort_values(ascending=False).index))
csv_sel = ventas.exportar_csv({**f_mes, "cliente": ["MELI"]}, "Lavadoras").lstrip("\ufeff").split("\r\n")
csv_todo = ventas.exportar_csv({**f_mes, "cliente": ["MELI"]}).lstrip("\ufeff").split("\r\n")
prueba("exportar: Clasif2 | Producto | Venta, solo la elegida y todas", csv_sel[0] == "Clasif2;Producto;Venta" and {x.split(";")[0] for x in csv_sel[1:] if x} == {"Lavadoras"}
       and {x.split(";")[0] for x in csv_todo[1:] if x} == set(e2.index) and sum(int(x.split(";")[2]) for x in csv_todo[1:] if x) == int(e2.sum()))
cols = ["Country", "Order", "Sequence", "ID_SKU", "Quantity_SKU", "Category_Ids_Sku", "Reference_Code", "SKU_Name", "SKU_Value", "SKU_Selling_Price",
        "Item_Attachments", "warehouse", "SLA_type", "List_freight_price", "Freight_price", "Shipping_Estimate_Date"]
fila = pd.DataFrame([["CH", "O1", "1", "9", 2, "/1/", "240096077", "Secadora 9Kg", 1939900, 1939900, "", "EC01", "Conv", 0, 0, None]], columns=cols)
d_it, inf = items.normalizar(fila, pd.Series({"1": 38798.0}))
prueba("columnas reales de OrderItems (SKU_Selling_Price en centavos)", inf["mapa"]["precio_unitario"] == "SKU_Selling_Price" and inf["centavos"] and cerca(d_it["Monto"].iloc[0], 38798))

print("Memoria del asistente (historial y valoracion)")
import tempfile  # noqa: E402

from app.asistente import memoria  # noqa: E402

hist = tempfile.mktemp(suffix=".jsonl")
memoria.reiniciar_para_pruebas(hist)
r1 = p("cuantas unidades del med165b hoy")
prueba("la pregunta queda en el historial", bool(r1.get("id")) and memoria.estadisticas()["preguntas"] == 1)
memoria.valorar(r1["id"], True)
prueba("una pregunta validada se repite desde la memoria", p("cuantas unidades del MED165B hoy?")["via"] == "memoria")
r2 = p("pedidos cancelados hoy")
memoria.valorar(r2["id"], False)
prueba("una respuesta rechazada avisa la proxima vez", any("no te sirvió" in n for n in p("pedidos cancelados hoy")["notas"]))
memoria.reiniciar_para_pruebas(hist)
prueba("el historial sobrevive a un reinicio del servidor", memoria.estadisticas()["preguntas"] >= 3 and memoria.exacta("cuantas unidades del med165b hoy") is not None)
p("blablabla")
prueba("registra lo que no entendio para mejorar las reglas", ("blablabla", 1) in memoria.estadisticas()["no_entendidas"])
r3 = p("y ayer?", r1["plan"])
prueba("un seguimiento no se guarda como pregunta reutilizable", memoria.exacta("y ayer") is None)
memoria.valorar(r3["id"], True)
prueba("un seguimiento validado tampoco se reutiliza (depende del contexto)", memoria.exacta("y ayer") is None)
p("cuantas unidades del med165b hoy")
prueba("las preguntas repetidas pasan a ser frecuentes", "cuantas unidades del med165b hoy" in memoria.frecuentes() or "cuantas unidades del MED165B hoy?" in memoria.frecuentes())

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} falla(s): " + "; ".join(fallos))
    sys.exit(1)
print("RESULTADO: todo en orden")
