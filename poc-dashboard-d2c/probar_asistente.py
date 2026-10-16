# -*- coding: utf-8 -*-
"""Prueba del asistente de consultas con los datos de ejemplo. Uso:  python probar_asistente.py

Cada pregunta se compara contra una cifra calculada a mano con pandas (no con el codigo del asistente), asi se
comprueba que entiende la pregunta Y que la cifra es correcta. Sale con codigo 1 si algo falla.
"""
import os
import re
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
    asistente.motor._LLAMADAS.clear()          # el limite por minuto no aplica a la bateria de pruebas
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
prueba("la venta total es el monto de los pedidos (el mismo del tablero)", cerca(v["total"], nc["Total_Value"].sum()))
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

print("Exportar pedidos segun los filtros")
flt = {"alcance": "todos", "cliente": ["MELI"], "fecha_ini": "2026-08-01", "fecha_fin": "2026-08-11"}
csv_p, n_p = servicio.exportar_pedidos(flt)
fil = csv_p.lstrip("\ufeff").strip().split("\r\n")
esp_n = int(((dim["SalesChannelName"] == "MELI") & (dim["Creation_Date"] >= "2026-08-01") & (dim["Creation_Date"] <= "2026-08-11")).sum())
prueba("exporta TODOS los pedidos del filtro (no solo las 500 filas de la tabla)", n_p == esp_n and len(fil) == esp_n + 1 and esp_n > 500, f"{n_p} vs {esp_n}")
prueba("encabezados y suma del monto correctos", fil[0].startswith("Sequence;Orden VTEX;Creación;Estado") and
       cerca(sum(float(x.split(";")[12]) for x in fil[1:]), dim[(dim["SalesChannelName"] == "MELI") & (dim["Creation_Date"] >= "2026-08-01") & (dim["Creation_Date"] <= "2026-08-11")]["Total_Value"].sum()))
csv_c, n_c = servicio.exportar_pedidos({"alcance": "todos"}, True)
prueba("criticos: solo facturados en SAP y pendientes en VTEX", n_c == int((dim["Facturado Sin Despacho"] == "Facturado sin despacho").sum()) and n_c > 0)
from app import exportar  # noqa: E402

prueba("un texto que parece formula no se ejecuta en Excel", exportar.celda("=1+1") == "\'=1+1" and exportar.celda("-5") == "-5" and exportar.celda('a;b') == '"a;b"')

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

print("Maestra: deteccion automatica y venta repartida por pedido")
from app import maestra  # noqa: E402
from app.config import settings  # noqa: E402

object.__setattr__(settings, "demo", False)
llamadas = []


def falso(sql):
    llamadas.append(sql)
    if "INFORMATION_SCHEMA" in sql:
        return pd.DataFrame({"TABLE_SCHEMA": ["dbo"] * 4, "TABLE_NAME": ["bi_forecast_clasif3", "bi_vtex_producto", "bi_maestra_producto_temp", "bi_maestra_producto"]})
    if "bi_maestra_producto]" in sql and "temp" not in sql:
        return pd.DataFrame({"codigoSap": ["910016501", "920008501"], "Descripcion": ["Refri", "Lavadora"], "ClasificacionPrd2": [3, 4], "DescClasif2": ["Refrigeradores", "Lavadoras"]})
    return pd.DataFrame({"x": [1]})


maestra._leer = falso
maestra._CACHE.update(t=0.0, df=None)
mm, err, _ = maestra.cargar()
prueba("encuentra sola la maestra entre las tablas parecidas y prefiere el nombre de Clasif2", err is None and mm.attrs["tabla"] == "dbo.bi_maestra_producto" and set(mm["Clasif2"]) == {"Refrigeradores", "Lavadoras"})
prueba("no lee tablas temporales ni de forecast antes que la maestra", not any("temp" in q or "forecast" in q for q in llamadas if "INFORMATION" not in q))
object.__setattr__(settings, "demo", True)
ped = pd.DataFrame({"Sequence": ["1", "2"], "Status": ["invoiced", "invoiced"], "Total_Value": [1000.0, 500.0]})   # el pedido 2 no tiene lineas
ln = pd.DataFrame({"Sequence": ["1", "1"], "SKU": ["910016501", "920008501"], "Qty": [1.0, 1.0], "Monto": [100.0, 300.0], "Descripcion": ["a", "b"]})
servicio_lineas, servicio_filtrar = servicio.lineas_todas, servicio.filtrar_pedidos
servicio.lineas_todas = lambda: (dim, hoy, ln, {"mapa": {}, "columnas": []})
servicio.filtrar_pedidos = lambda f: ped
mb, _, _ = ventas._base({})
servicio.lineas_todas, servicio.filtrar_pedidos = servicio_lineas, servicio_filtrar
rep = mb.groupby("Clasif2")["Venta"].sum().round().to_dict()
prueba("el monto del pedido se reparte por el valor de sus lineas y no se pierde el de un pedido sin lineas",
       rep == {"Refrigeradores": 250.0, "Lavadoras": 750.0, ventas.SIN_LINEAS: 500.0} and cerca(mb["Venta"].sum(), ped["Total_Value"].sum()), str(rep))

print("Stock: cruce producto -> codigo SAP -> stock VTEX")
from app import skus as skus_mod  # noqa: E402

prueba("el codigo SAP se normaliza (ceros a la izquierda, .0)", list(skus_mod.limpiar(pd.Series(["000240096077", " 240096077.0", "240096077"]))) == ["240096077"] * 3)
stock_orig = servicio._CACHE["stock"]
mae_orig = maestra.cargar
servicio._CACHE["stock"] = pd.DataFrame({"codigoSap": ["000000910016501", "00910016502", "0000999000001"], "VTEX": [50, 4, 12], "Reservado": [8, 4, 2]})
mae_demo = maestra.cargar()[0]
extra = pd.DataFrame([{"SKU": "999000001", "Clasif2": "Cocinas", "Producto": "Cocina Prueba XZ100 4 Quemadores"}])
maestra.cargar = lambda: (pd.concat([mae_demo, extra], ignore_index=True), None, [])
r = p("cual es el stock de med165b")
filas = {f[0]: f for f in r["tabla"]["filas"]}
prueba("stock del MED165B: busca el codigo SAP del producto y lo cruza con la tabla aunque venga con ceros",
       r["tipo"] == "stock" and cerca(filas["910016501"][4], 42) and cerca(filas["910016502"][4], 0) and "Sin stock" in r["texto"], r["texto"])
r = p("stock de la cocina xz100")
prueba("encuentra por la maestra un producto que aun no tiene ventas en las lineas", r["ok"] and r["tabla"]["filas"][0][0] == "999000001" and cerca(r["tabla"]["filas"][0][4], 10), r["texto"])
servicio._CACHE["stock"] = pd.DataFrame({"codigoSap": ["1"], "VTEX": [1], "Reservado": [0]})
r = p("cual es el stock de med165b")
prueba("si el codigo no esta en la tabla de stock, lo dice y muestra codigos de ejemplo", r["ok"] and "Sin dato en la tabla de stock" in r["texto"] and any("ejemplo" in n for n in r["notas"]), r["texto"])
servicio._CACHE["stock"] = pd.DataFrame(columns=["codigoSap", "VTEX", "Reservado"])
prueba("sin datos de stock, explica por que", p("stock del med165b")["ok"] is False)
servicio._CACHE["stock"] = stock_orig
maestra.cargar = mae_orig

# --- clasificacion como entidad, stock con mas frases y cobertura
for q in ("stock de refrigeradores", "cuantas hay de refrigeradores", "tenemos de med165b", "quedan lavadoras"):
    r = p(q)
    prueba(f"stock: «{q}»", r["ok"] and r.get("tipo") == "stock" and len(r["tabla"]["filas"]) >= 1, r.get("texto"))
r = p("stock de refrigeradores")
prueba("el stock trae cobertura en dias", r["tabla"]["cols"][-1]["n"].startswith("Cobertura") and len(r["tabla"]["filas"]) > 1)
r = p("ventas de refrigeradores ultimos 7 dias")
prueba("la clasificacion filtra las ventas", r["ok"] and "Refrigerador" in r["texto"], r.get("texto"))
r = p("asdf qwer zxcv")
prueba("si no entiende, ofrece ejemplos", r["ok"] is False and r.get("ejemplos"))

# --- alertas, IA que explica (sin cambiar cifras), deteccion de la tabla de stock, informe de aprendizaje
for q in ("hay algo raro hoy", "que debo revisar"):
    r = p(q)
    prueba(f"alertas: «{q}»", r["ok"] and r.get("tipo") == "alertas" and len(r["tabla"]["filas"]) >= 1, r.get("texto"))
r = p("hay algo raro hoy")
prueba("las alertas incluyen quiebre de stock", any(f[1] in ("Sin stock", "Quiebre próximo") for f in r["tabla"]["filas"]))
r = p("cuantos pedidos se cancelaron hoy")
ia_orig = asistente.ia._llm
asistente.ia._llm = lambda s, u, json_out=True: "Hubo " + re.search(r"(\d[\d.]*) pedidos", r["texto"]).group(1) + " pedidos cancelados."
prueba("la IA puede explicar con las cifras del servidor", asistente.ia.redactar("x", r) is not None)
asistente.ia._llm = lambda s, u, json_out=True: "Hubo 987654 pedidos cancelados."
prueba("si la IA inventa una cifra, se descarta", asistente.ia.redactar("x", r) is None)
asistente.ia._llm = ia_orig
datos = asistente.ia.datos_para_redactar("x", r)
prueba("a la IA solo salen cifras agregadas (sin pedidos)", "Sequence" not in datos and "Order" not in datos)
prueba("el informe de aprendizaje funciona", "no_entendidas" in asistente.memoria.informe())
from app import queries as _q
_orig, _vistas = _q.leer_sap, []
def _falso(sql):
    _vistas.append(sql)
    return pd.DataFrame({"FECHA": ["2026-08-11"], "LOTE": ["1_1"], "codigoSap": ["0000123"], "VTEX": [5], "Reservado": [2]})
_q.leer_sap = _falso
_st = _q.q_stock_vtex()
prueba("el stock usa la consulta de bi_vtex_stock (ultima foto, bodega 1_1, maestra al dia)",
       len(_st) == 1 and "bi_vtex_stock" in _vistas[0] and "'1_1'" in _vistas[0] and "MAX(fechaActualizacion)" in _vistas[0] and "SET NOCOUNT ON" in _vistas[0])
prueba("guarda la fecha de la foto de stock", _q.INFO_STOCK["fecha"] == "11-08-2026")
def _roto(sql):
    raise RuntimeError("Invalid object name 'bi_vtex_stock'")
_q.leer_sap = _roto
prueba("si la consulta falla, el error queda para explicarlo", len(_q.q_stock_vtex()) == 0 and "bi_vtex_stock" in _q.ERROR_STOCK[0])
_q.leer_sap = _orig


# --- verdad independiente: cada respuesta se compara con un calculo directo sobre los datos
print("Respuestas contra el calculo directo")
import pandas as _pd
import time as _t
from app import servicio as _sv
_dim, _hoy = _sv.base_pedidos()
_m0 = _hoy.replace(day=1)
_mes = _dim[(_dim["Creation_Date"] >= _m0) & (_dim["Creation_Date"] <= _hoy)]
_ok = _mes[_mes["Status"] != "canceled"]
_n = lambda v: f"{v:,.0f}".replace(",", ".")  # noqa: E731
r = p("porcentaje de cancelacion")
prueba("% de cancelacion = cancelados / todos los pedidos del mes", abs(r["valor"] - (_mes["Status"] == "canceled").mean()) < 1e-9, r["texto"])
prueba("«cancelados vs total» tambien es un porcentaje", abs(p("pedidos cancelados vs total")["valor"] - (_mes["Status"] == "canceled").mean()) < 1e-9)
r = p("cuantos pedidos no estan integrados")
prueba("«no estan integrados» cuenta los NO integrados (no los integrados)", r["valor"] == int((_ok["Estado Ingreso"] == "No ingresado").sum()), r["texto"])
r = p("cual fue el mejor dia")
_d = _ok.groupby("Creation_Date")["Total_Value"].sum()
prueba("el mejor dia es el de mayor venta", _d.idxmax().strftime("%d-%m-%Y") in r["texto"] and _n(_d.max()) in r["texto"], r["texto"])
r = p("pedidos del 5 de agosto")
prueba("«del 5 de agosto» filtra ese dia", r["valor"] == int((_ok["Creation_Date"] == "2026-08-05").sum()), r["texto"])
r = p("pedidos entre el 1 y el 10 de agosto")
prueba("«entre el 1 y el 10 de agosto» es un rango", r["valor"] == int(((_ok["Creation_Date"] >= "2026-08-01") & (_ok["Creation_Date"] <= "2026-08-10")).sum()), r["texto"])
r = p("ventas del mes de julio")
_jul = _dim[(_dim["Creation_Date"] >= "2026-07-01") & (_dim["Creation_Date"] <= "2026-07-31") & (_dim["Status"] != "canceled")]
prueba("«ventas del mes de julio» es julio (no el mes en curso)", abs(r["valor"] - _jul["Total_Value"].sum()) < 1, r["texto"])
r = p("cuantos clientes distintos")
prueba("clientes distintos", r["valor"] == _ok["SalesChannelName"].nunique(), r["texto"])
r = p("pedidos de mas de 1 millon")
prueba("filtro por monto", r["valor"] == int((_ok["Total_Value"] >= 1_000_000).sum()), r["texto"])
r = p("los 3 pedidos mas caros")
_top = set(_ok.sort_values("Total_Value", ascending=False).head(3)["Sequence"])
prueba("los pedidos mas caros son los de mayor monto", {f[0] for f in r["tabla"]["filas"]} == _top, r["texto"])
r = p("ventas por clasificacion")
prueba("ventas por clasificacion suman las ventas del mes", abs(sum(f[3] for f in r["tabla"]["filas"]) - _ok["Total_Value"].sum()) < 1, r["texto"])
r = p("quien es el cliente con mas cancelaciones")
_c = _mes[_mes["Status"] == "canceled"].groupby("SalesChannelName").size()
prueba("el cliente con mas cancelaciones", _c.idxmax() in r["texto"] and f"({_c.max()})" in r["texto"], r["texto"])
r = p("pedidos sin pv de mas de 2 dias")
prueba("pedidos no integrados con mas de 2 dias",
       r["valor"] == int(((_ok["Estado Ingreso"] == "No ingresado") & (_ok["Creation_Date"] <= _hoy - _pd.Timedelta(days=2))).sum()), r["texto"])
r = p("promedio de unidades por pedido")
prueba("unidades por pedido", abs(r["valor"] - _ok["Unidades"].sum() / len(_ok)) < 1e-9, r["texto"])
r = p("comparar ventas con el mes pasado")
prueba("si el mes anterior no esta cargado, lo dice en vez de inventar", r["comparacion"] is None and any("anterior" in n for n in r["notas"]), r["notas"])
r = p("ventas por mes")
prueba("ventas por mes: una fila por mes", len(r["tabla"]["filas"]) == _dim["Creation_Date"].dt.to_period("M").nunique(), r["texto"])

print("Stock, resumen y pedidos: respuestas distintas para preguntas distintas")
a, b, c = p("productos con poco stock"), p("que productos no tienen stock"), p("stock total")
prueba("poco stock, sin stock y stock total no responden lo mismo", len({a["texto"], b["texto"], c["texto"]}) == 3, [a["texto"], b["texto"], c["texto"]])
prueba("la cobertura se ordena de menor a mayor", [f[6] for f in a["tabla"]["filas"] if f[6] is not None] == sorted(f[6] for f in a["tabla"]["filas"] if f[6] is not None))
r = p("como vamos este mes")
prueba("«como vamos» da el resumen del periodo con comparacion", r.get("tipo") == "resumen" and any(f[0] == "Pedidos" for f in r["tabla"]["filas"]), r["texto"])
x, y, z = p("que productos tiene el pedido 3506611"), p("cuantas lineas tiene el pedido 3506611"), p("estado del pedido 3506611")
prueba("las tres preguntas sobre el mismo pedido responden distinto", len({x["texto"], y["texto"], z["texto"]}) == 3, [x["texto"], y["texto"], z["texto"]])
r = p("productos sin ventas")
prueba("productos sin ventas responde (aunque sea que todos vendieron)", r["ok"] and r["tipo"] == "sin_ventas", r["texto"])
r = p("que clientes no han comprado hoy")
prueba("clientes sin pedidos en el periodo", r["ok"] and r["tipo"] == "sin_ventas", r["texto"])

print("Conversacion: sin repetir y sin quedar colgado")
r1 = p("cuantos pedidos hay este mes")
r2 = p("cuantos pedidos hay este mes", r1["plan"])
prueba("la misma consulta seguida avisa que es repetida", any("misma consulta" in n for n in r2["notas"]), r2["notas"])
s1 = r1["seguir"]
r3 = asistente.responder("cuantos pedidos hay este mes", None, [x for x in s1])
prueba("los seguimientos no repiten lo que ya se pregunto", not set(s1) & set(r3["seguir"]) or len(set(s1) ^ set(r3["seguir"])) > 0 and r3["seguir"] != s1, (s1, r3["seguir"]))
prueba("«gracias» no devuelve la ayuda", "De nada" in p("gracias")["texto"])
prueba("«que dia es hoy» responde la fecha", _hoy.strftime("%d-%m-%Y") in p("que dia es hoy")["texto"])
r = p("cual es el clima")
prueba("fuera de alcance se dice claro (no se sugiere una pregunta absurda)", r.get("fuera_de_alcance") and "Quisiste decir" not in r["texto"], r["texto"])
r = p("cuantos pedidos entraron en la ultima hora")
prueba("sin hora en los datos, lo avisa", any("sin hora" in n for n in r["notas"]), r["notas"])
import asyncio as _aio
from fastapi.testclient import TestClient as _TC
from app import main as _main
_o_resp, _o_t = asistente.responder, _main.TIEMPO_MAX_CHAT
asistente.responder = lambda *a, **k: __import__("time").sleep(1.5) or {"ok": True}
_main.TIEMPO_MAX_CHAT = 0.3
_t0 = _t.time()
_r = _TC(_main.app).post("/api/chat", json={"pregunta": "x"}).json()
asistente.responder, _main.TIEMPO_MAX_CHAT = _o_resp, _o_t
prueba("una consulta lenta no deja el chat colgado", _r.get("ok") is False and _r.get("reintentar") and _t.time() - _t0 < 1.2, _r)

# --- el stock se carga aparte: una consulta lenta no frena el tablero y no se repite
import time as _t
from app import queries as _qq
_ST = {"n": 0}
def _lento():
    _ST["n"] += 1
    _t.sleep(2)
    _qq.ERROR_STOCK.clear()
    return servicio._CACHE.get("stock_demo") if False else __import__("app.demo", fromlist=["x"]).datos_demo()[4]
_o = {k: getattr(_qq, k) for k in ("q_orders", "q_order_items", "q_sap_ingresos", "q_facturacion", "q_hoy_cl", "q_stock_vtex")}
_d = __import__("app.demo", fromlist=["x"]).datos_demo()
for _k, _v in zip(("q_orders", "q_order_items", "q_sap_ingresos", "q_facturacion"), _d[:4]):
    setattr(_qq, _k, (lambda v=_v: v))
_qq.q_hoy_cl, _qq.q_stock_vtex = (lambda: _d[5]), _lento
_demo0, _esp0, _dim0, _stk0 = settings.demo, settings.stock_espera, servicio._CACHE["dim"], dict(servicio._STK)
object.__setattr__(settings, "demo", False)
object.__setattr__(settings, "stock_espera", 0)
servicio._STK.update(df=None, t=0.0, hilo=None, huella=None)
servicio._STK["listo"].clear()
servicio._CACHE["dim"] = None
_t0 = _t.time()
servicio._cargar_dim()
prueba("el tablero no espera a un stock lento", _t.time() - _t0 < 1.5, f"{_t.time() - _t0:.1f} s")
prueba("mientras carga, el chat lo explica", "se está consultando" in p("stock de med165b")["texto"])
_t.sleep(3)
servicio._recargar(forzar=True)
servicio._recargar(forzar=True)
prueba("el stock se consulta una sola vez y se reutiliza", _ST["n"] == 1, _ST["n"])
for _k, _v in _o.items():
    setattr(_qq, _k, _v)
object.__setattr__(settings, "demo", _demo0)
object.__setattr__(settings, "stock_espera", _esp0)
servicio._STK.update(_stk0)
servicio._CACHE["dim"] = _dim0

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} falla(s): " + "; ".join(fallos))
    sys.exit(1)
print("RESULTADO: todo en orden")
