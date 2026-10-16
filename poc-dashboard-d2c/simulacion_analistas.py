"""Simulacion de un equipo de analistas que usa el asistente.

1. Cada analista (ventas, tendencias, clientes, productos, stock, logistica, finanzas, operacion, ventanas de tiempo) aporta preguntas SEMILLA
   (mas de 100), cada una con la INTENCION que deberia entender el asistente (accion, metrica, agrupacion, filtros, periodo...).
2. De cada semilla se generan variantes: otros periodos, clientes, productos, bodegas, formas de redactar y errores de tipeo.
   Total: mas de 500 preguntas distintas, cada una con su intencion esperada derivada de la semilla y de lo que se sustituyo.
3. Todas pasan por el asistente (sin IA, con los datos de ejemplo). Se mide si entendio lo esperado y si respondio sin error.

Uso:   python simulacion_analistas.py [--minimo 500] [--escribir]      (--escribir guarda simulacion/*.csv e INFORME.md)
Sale con codigo 1 si la tasa de comprension baja de --umbral (por defecto 0.95)."""
from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("DEMO", "1")
import pandas as pd  # noqa: E402

from app import servicio  # noqa: E402
from app.asistente import memoria, motor, responder  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "simulacion"

# ------------------------------------------------------------------ ranuras: lo que se sustituye y lo que eso implica
PERIODOS = [("hoy", "hoy", {"periodo": "hoy"}), ("ayer", "ayer", {"periodo": "ayer"}),
            ("esta semana", "de esta semana", {"periodo": "semana"}), ("la semana pasada", "de la semana pasada", {"periodo": "semana_anterior"}),
            ("este mes", "de este mes", {"periodo": "mes"}), ("el mes pasado", "del mes pasado", {"periodo": "mes_anterior"}),
            ("en los ultimos 7 dias", "de los ultimos 7 dias", {"periodo": "ultimos", "dias": 7}),
            ("en los ultimos 30 dias", "de los ultimos 30 dias", {"periodo": "ultimos", "dias": 30})]
CLIENTES = ["MELI", "Falabella", "Mademsa", "Ripley", "Paris", "Electrolux", "Fensa", "Walmart"]
PRODUCTOS = ["med165b", "lavadoras", "refrigeradores", "cocinas", "ls 12", "microondas", "lavavajillas", "frigobar"]
CLASIF = ["refrigeradores", "lavadoras", "cocinas", "microondas"]
BODEGAS = [("POST Fechado", "POST_Fechado"), ("post fechado", "POST_Fechado"), ("EC01", "EC01")]
PREFIJOS = ["", "", "", "oye ", "necesito saber ", "por favor ", "me puedes decir ", "quiero ver ", "dime ", "consulta: ", "una duda, ", "hola, "]
SUFIJOS = ["", "", "", "?", " porfa", " por favor", " gracias"]


def ruido_texto(q: str, r: random.Random) -> str:
    """Formas de escribir distintas: mayusculas, sin signos, signos de interrogacion, espacios de mas."""
    t = r.choice(["igual", "igual", "mayus", "titulo", "pregunta", "espacios"])
    if t == "mayus":
        return q.upper()
    if t == "titulo":
        return q[:1].upper() + q[1:]
    if t == "pregunta":
        return "¿" + q + "?"
    if t == "espacios":
        return "  " + q.replace(" ", "  ", 1) + " "
    return q


def sin_tilde(q: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", q) if not unicodedata.combining(c))


def errata(palabra: str, r: random.Random) -> str:
    if len(palabra) < 7:
        return palabra
    i = r.randrange(2, len(palabra) - 2)
    return palabra[:i] + palabra[i + 1:]                                    # se come una letra


# ------------------------------------------------------------------ semillas: (rol, plantilla, intencion esperada)
# Ranuras: {P} periodo adverbial ("este mes"), {D} periodo con "de" ("de este mes"), {C}/{C2} cliente, {PR} producto, {K} clasificacion, {B} bodega, {SEQ} pedido
S = []


def semilla(rol, plantilla, **esperado):
    S.append((rol, plantilla, esperado))


# --- ventas
for pl in ("cuanto vendimos {P}", "ventas {D}", "monto total vendido {P}", "total de ventas {D}"):
    semilla("ventas", pl, metrica="monto", accion="medir")
semilla("ventas", "cuanto facturamos {P}", metrica="monto", accion="medir", estado=["facturado"])
semilla("ventas", "cual es el ticket promedio {D}", metrica="ticket")
semilla("ventas", "cuantos pedidos tuvimos {P}", metrica="pedidos")
semilla("ventas", "cuantas unidades se vendieron {P}", metrica="unidades")
semilla("ventas", "ventas de {PR} {D}", metrica="monto", producto=True)
semilla("ventas", "cuantas unidades de {PR} vendimos {P}", metrica="unidades", producto=True)
semilla("ventas", "ventas de {C} {D}", metrica="monto", cliente=["{C}"])
semilla("ventas", "cuanto compro {C} {P}", metrica="monto", cliente=["{C}"])
semilla("ventas", "ventas por dia {D}", metrica="monto", agrupar="dia")
semilla("ventas", "ventas por cliente {D}", metrica="monto", agrupar="cliente")
semilla("ventas", "ventas por canal {D}", metrica="monto", agrupar="canal")
semilla("ventas", "ventas por bodega {D}", metrica="monto", agrupar="bodega")
semilla("ventas", "ventas por clasificacion {D}", metrica="monto", agrupar="clasif2")
semilla("ventas", "ventas por categoria {D}", metrica="monto", agrupar="clasif2")
semilla("ventas", "top 5 productos mas vendidos {D}", agrupar="producto", top=5)
semilla("ventas", "top 3 clientes por monto {D}", agrupar="cliente", top=3, metrica="monto")
semilla("ventas", "ventas facturadas {D}", metrica="monto", estado=["facturado"])
semilla("ventas", "unidades por producto {D}", metrica="unidades", agrupar="producto")
# --- tendencias y comparaciones
semilla("tendencias", "evolucion de ventas {D}", metrica="monto", agrupar="dia")
semilla("tendencias", "ventas diarias {D}", metrica="monto", agrupar="dia")
semilla("tendencias", "evolucion de los pedidos {D}", metrica="pedidos", agrupar="dia")
semilla("tendencias", "ventas semanales", metrica="monto", agrupar="semana")
semilla("tendencias", "ventas por mes", metrica="monto", agrupar="mes")
semilla("tendencias", "comparar ventas {D} con el periodo anterior", metrica="monto", comparar=True)
semilla("tendencias", "ventas de este mes vs el mes pasado", metrica="monto", comparar=True, periodo="mes")
semilla("tendencias", "pedidos de esta semana comparado con la semana pasada", metrica="pedidos", comparar=True, periodo="semana")
semilla("tendencias", "como vamos este mes", accion="resumen", periodo="mes")
semilla("tendencias", "como vamos hoy", accion="resumen", periodo="hoy")
semilla("tendencias", "resumen {D}", accion="resumen")
semilla("tendencias", "que dia se vendio mas {D}", agrupar="dia", orden="desc", top=1)
semilla("tendencias", "cual fue el mejor dia {D}", agrupar="dia", orden="desc", top=1)
semilla("tendencias", "que dia hubo menos pedidos {D}", agrupar="dia", orden="asc", top=1)
# --- clientes
semilla("clientes", "cual es el cliente que mas compra {P}", agrupar="cliente", orden="desc", top=1)
semilla("clientes", "ranking de clientes por monto {D}", agrupar="cliente", metrica="monto")
semilla("clientes", "pedidos por cliente {D}", agrupar="cliente", metrica="pedidos")
semilla("clientes", "cuantos clientes distintos compraron {P}", metrica="distintos", agrupar="cliente")
semilla("clientes", "que clientes no han comprado {P}", accion="sin_ventas", agrupar="cliente")
semilla("clientes", "ticket promedio por cliente {D}", metrica="ticket", agrupar="cliente")
semilla("clientes", "pedidos cancelados por cliente {D}", estado=["cancelado"], agrupar="cliente")
semilla("clientes", "quien es el cliente con mas cancelaciones {P}", estado=["cancelado"], agrupar="cliente", top=1)
semilla("clientes", "pedidos de {C} {P}", metrica="pedidos", cliente=["{C}"])
semilla("clientes", "ventas de {C} y {C2} {D}", metrica="monto", clientes_ambos=True)
semilla("clientes", "cuantos pedidos pendientes tiene {C}", estado=["pendiente"], cliente=["{C}"])
semilla("clientes", "mejor cliente {D}", agrupar="cliente", orden="desc", top=1)
# --- clasificacion y producto
semilla("productos", "ventas de {K} {D}", metrica="monto", producto=True)
semilla("productos", "que clasificacion vende mas {P}", agrupar="clasif2", orden="desc", top=1)
semilla("productos", "ventas de cada clasificacion {D}", agrupar="clasif2")
semilla("productos", "cuantos productos distintos se vendieron {P}", metrica="distintos", agrupar="producto")
semilla("productos", "productos sin ventas {P}", accion="sin_ventas")
semilla("productos", "producto mas vendido {D}", agrupar="producto", orden="desc")
semilla("productos", "productos menos vendidos {D}", agrupar="producto", orden="asc")
semilla("productos", "cuanto vendimos de {PR} {P}", metrica="monto", producto=True)
semilla("productos", "pedidos que incluyen {PR} {D}", producto=True)
semilla("productos", "ventas de {PR} por cliente {D}", producto=True, agrupar="cliente")
semilla("productos", "unidades de {PR} por dia {D}", producto=True, agrupar="dia")
# --- stock
semilla("stock", "cual es el stock de {PR}", accion="stock", producto=True)
semilla("stock", "hay stock de {PR}", accion="stock", producto=True)
semilla("stock", "cuantas unidades quedan de {PR}", accion="stock", producto=True)
semilla("stock", "que productos no tienen stock", accion="stock", stock_modo="sin")
semilla("stock", "productos con poco stock", accion="stock", stock_modo="poco")
semilla("stock", "cobertura de stock", accion="stock", stock_modo="cobertura")
semilla("stock", "dias de inventario de {PR}", accion="stock", stock_modo="cobertura", producto=True)
semilla("stock", "stock total", accion="stock", stock_modo="todo")
semilla("stock", "que productos se van a quebrar", accion="stock", stock_modo="poco")
semilla("stock", "stock de {K}", accion="stock", producto=True)
semilla("stock", "tenemos {PR} disponible", accion="stock", producto=True)
semilla("stock", "pedidos pendientes por quiebre de stock {D}", estado=["quiebre"])
semilla("stock", "cuantos pedidos estan esperando por falta de stock", estado=["quiebre"])
# --- logistica y entregas
semilla("logistica", "cuantos pedidos estan atrasados", estado=["vencido"])
semilla("logistica", "pedidos con entrega vencida por cliente", estado=["vencido"], agrupar="cliente")
semilla("logistica", "cual es el sla con mas atrasos", estado=["vencido"], agrupar="sla", top=1)
semilla("logistica", "pedidos por sla {D}", agrupar="sla")
semilla("logistica", "pedidos por bodega {D}", agrupar="bodega")
semilla("logistica", "cuantos pedidos de {B} hay {P}", bodega=["{BE}"])
semilla("logistica", "pedidos pendientes {P}", estado=["pendiente"])
semilla("logistica", "cuantos pedidos se cancelaron {P}", estado=["cancelado"])
semilla("logistica", "porcentaje de cancelacion {D}", metrica="pct_estado", estado=["cancelado"])
semilla("logistica", "pedidos facturados sin despacho", estado=["sin_despacho"])
semilla("logistica", "status de {B} {P}", agrupar="status", bodega=["{BE}"])
# --- finanzas e integracion
semilla("finanzas", "porcentaje de integracion {D}", metrica="pct_integracion")
semilla("finanzas", "cuantos pedidos no estan integrados {P}", estado=["no_integrado"])
semilla("finanzas", "cuanto monto esta en riesgo", metrica="monto_riesgo")
semilla("finanzas", "cuanto tarda un pedido en integrarse", metrica="desfase")
semilla("finanzas", "pedidos sin pv de mas de 2 dias", estado=["no_integrado"], edad_min=2)
semilla("finanzas", "pedidos de mas de 1 millon {D}", monto_min=1_000_000)
semilla("finanzas", "pedidos de menos de 50 mil {D}", monto_max=50_000)
semilla("finanzas", "los 10 pedidos mas caros {D}", accion="listar", metrica="monto", orden="desc", top=10)
semilla("finanzas", "pedido de mayor monto {D}", accion="listar", metrica="monto", orden="desc", top=1)
semilla("finanzas", "monto de pedidos pendientes {P}", metrica="monto", estado=["pendiente"])
# --- operacion
semilla("operacion", "hay algo raro hoy", accion="alertas")
semilla("operacion", "que debo revisar", accion="alertas")
semilla("operacion", "que esta en riesgo", accion="alertas")
semilla("operacion", "hay alertas", accion="alertas")
semilla("operacion", "cuantos pedidos entraron en la ultima hora", periodo="hoy")
semilla("operacion", "dame el listado de pedidos cancelados {P}", accion="listar", estado=["cancelado"])
semilla("operacion", "pedido {SEQ}", accion="pedido")
semilla("operacion", "que productos tiene el pedido {SEQ}", accion="pedido", foco="productos")
semilla("operacion", "cuantas lineas tiene el pedido {SEQ}", accion="pedido", foco="lineas")
semilla("operacion", "estado del pedido {SEQ}", accion="pedido", foco="estado")
# --- ventanas de tiempo
semilla("tiempo", "pedidos del 5 de agosto", periodo="rango", desde="2026-08-05", hasta="2026-08-05")
semilla("tiempo", "ventas entre el 1 y el 10 de agosto", periodo="rango", desde="2026-08-01", hasta="2026-08-10", metrica="monto")
semilla("tiempo", "ventas de julio", periodo="rango", desde="2026-07-01", hasta="2026-07-31", metrica="monto")
semilla("tiempo", "ventas del lunes", periodo="rango", desde="2026-08-10", hasta="2026-08-10", metrica="monto")
semilla("tiempo", "ventas este año", periodo="rango", desde="2026-01-01", metrica="monto")
semilla("tiempo", "pedidos del ultimo trimestre", periodo="ultimos", dias=90)
semilla("tiempo", "ventas de la semana pasada por dia", periodo="semana_anterior", agrupar="dia")
semilla("tiempo", "pedidos hace 3 dias", periodo="rango", desde="2026-08-08", hasta="2026-08-08")
semilla("tiempo", "ventas del 15 de julio al 20 de julio", periodo="rango", desde="2026-07-15", hasta="2026-07-20", metrica="monto")
semilla("tiempo", "cuantos pedidos hubo el 3 de agosto", periodo="rango", desde="2026-08-03", hasta="2026-08-03")
semilla("tiempo", "ventas del viernes pasado", periodo="rango", desde="2026-08-07", hasta="2026-08-07", metrica="monto")
semilla("tiempo", "pedidos de agosto por cliente", periodo="rango", desde="2026-08-01", hasta="2026-08-31", agrupar="cliente")

# ------------------------------------------------------------------ RONDA 2: redaccion coloquial escrita sin mirar las reglas (prueba a ciegas)
RONDA2 = len(S)
semilla("ventas", "cuanta plata entro {P}", metrica="monto")
semilla("ventas", "como nos fue {P}", accion="resumen")
semilla("ventas", "cuanto se facturo {P}", metrica="monto", estado=["facturado"])
semilla("ventas", "dime las ventas totales {D}", metrica="monto")
semilla("ventas", "cuantas ordenes entraron {P}", metrica="pedidos")
semilla("ventas", "cuantos equipos de {PR} salieron {P}", metrica="unidades", producto=True)
semilla("ventas", "que tan bien vendio {C} {P}", metrica="monto", cliente=["{C}"])
semilla("ventas", "total vendido por {C} {P}", metrica="monto", cliente=["{C}"])
semilla("ventas", "cual es el valor promedio de cada pedido {D}", metrica="ticket")
semilla("ventas", "cuanto dejo cada cliente {D}", agrupar="cliente", metrica="monto")
semilla("tendencias", "como han ido las ventas dia a dia {D}", agrupar="dia", metrica="monto")
semilla("tendencias", "en que dia vendimos mas {D}", agrupar="dia", orden="desc", top=1)
semilla("tendencias", "cual fue el peor dia {D}", agrupar="dia", orden="asc", top=1)
semilla("tendencias", "las ventas subieron o bajaron {P} comparado con antes", metrica="monto", comparar=True)
semilla("tendencias", "dame un balance {D}", accion="resumen")
semilla("tendencias", "cual es el panorama {P}", accion="resumen")
semilla("tendencias", "como estamos {P}", accion="resumen")
semilla("tendencias", "venta mensual", agrupar="mes", metrica="monto")
semilla("clientes", "quienes son nuestros mejores clientes {D}", agrupar="cliente")
semilla("clientes", "quien nos compra mas {P}", agrupar="cliente", orden="desc", top=1)
semilla("clientes", "cuantos clientes hicieron pedidos {P}", metrica="distintos", agrupar="cliente")
semilla("clientes", "que cliente tiene mas pedidos cancelados {P}", estado=["cancelado"], agrupar="cliente", top=1)
semilla("clientes", "cuanto nos compro {C} {P}", metrica="monto", cliente=["{C}"])
semilla("clientes", "pedidos atrasados de {C}", estado=["vencido"], cliente=["{C}"])
semilla("clientes", "que ordenes hay de {C} {P}", cliente=["{C}"])
semilla("productos", "que es lo que mas se vende {P}", agrupar="producto", orden="desc")
semilla("productos", "cuales son los 5 productos estrella {D}", agrupar="producto", top=5)
semilla("productos", "que modelos casi no se venden {P}", agrupar="producto", orden="asc")
semilla("productos", "que categoria factura mas {P}", agrupar="clasif2", orden="desc", top=1)
semilla("productos", "reparto de ventas por familia de producto {D}", agrupar="clasif2")
semilla("productos", "cuantos modelos distintos vendimos {P}", metrica="distintos", agrupar="producto")
semilla("productos", "que productos no se han vendido {P}", accion="sin_ventas")
semilla("stock", "quedan {PR}", accion="stock", producto=True)
semilla("stock", "cuantos {PR} tenemos en bodega", accion="stock", producto=True)
semilla("stock", "hay existencias de {PR}", accion="stock", producto=True)
semilla("stock", "que modelos estan por acabarse", accion="stock", stock_modo="poco")
semilla("stock", "que se nos esta agotando", accion="stock", stock_modo="poco")
semilla("stock", "que productos estan agotados", accion="stock", stock_modo="sin")
semilla("stock", "para cuantos dias alcanza el stock de {PR}", accion="stock", stock_modo="cobertura", producto=True)
semilla("stock", "cuanto inventario tenemos en total", accion="stock", stock_modo="todo")
semilla("stock", "que pedidos estan detenidos por falta de stock", estado=["quiebre"])
semilla("logistica", "que pedidos van atrasados", estado=["vencido"])
semilla("logistica", "pedidos que ya pasaron su fecha de entrega", estado=["vencido"])
semilla("logistica", "cuantas ordenes siguen pendientes {P}", estado=["pendiente"], metrica="pedidos")
semilla("logistica", "cuantos pedidos se anularon {P}", estado=["cancelado"])
semilla("logistica", "que tanto se cancela {D}", metrica="pct_estado", estado=["cancelado"])
semilla("logistica", "pedidos ya facturados {P}", estado=["facturado"])
semilla("logistica", "que bodega despacha mas pedidos {P}", agrupar="bodega", orden="desc", top=1)
semilla("logistica", "cual es el tipo de despacho mas usado {P}", agrupar="sla", orden="desc", top=1)
semilla("finanzas", "cuantos pedidos no han llegado a sap {P}", estado=["no_integrado"])
semilla("finanzas", "cuantos dias demora un pedido en pasar a sap", metrica="desfase")
semilla("finanzas", "que porcentaje de pedidos ya esta en sap {D}", metrica="pct_integracion")
semilla("finanzas", "cuanta plata esta en juego por pedidos atrasados", metrica="monto_riesgo")
semilla("finanzas", "ordenes de mas de 500 mil pesos {D}", monto_min=500_000)
semilla("finanzas", "pedidos grandes de mas de 2 millones {D}", monto_min=2_000_000)
semilla("finanzas", "cual es el pedido mas caro {D}", accion="listar", metrica="monto", orden="desc", top=1)
semilla("finanzas", "muestrame los 5 pedidos de mayor valor {D}", accion="listar", metrica="monto", orden="desc", top=5)
semilla("operacion", "hay algun problema hoy", accion="alertas")
semilla("operacion", "que cosas debo atender primero", accion="alertas")
semilla("operacion", "algo anormal en las ventas", accion="alertas")
semilla("operacion", "pedidos sin ingresar de hace mas de 3 dias", estado=["no_integrado"], edad_min=3)
semilla("operacion", "detalle del pedido {SEQ}", accion="pedido")
semilla("operacion", "que lleva el pedido {SEQ}", accion="pedido", foco="productos")
semilla("operacion", "en que estado va el pedido {SEQ}", accion="pedido", foco="estado")
semilla("tiempo", "ventas del 1 al 7 de agosto", periodo="rango", desde="2026-08-01", hasta="2026-08-07", metrica="monto")
semilla("tiempo", "cuantos pedidos entraron el 10 de agosto", periodo="rango", desde="2026-08-10", hasta="2026-08-10")
semilla("tiempo", "ventas de este trimestre", periodo="rango", desde="2026-07-01", metrica="monto")
semilla("tiempo", "ventas del año hasta hoy", periodo="rango", desde="2026-01-01", metrica="monto")
semilla("tiempo", "pedidos de anteayer", periodo="rango", desde="2026-08-09", hasta="2026-08-09")
semilla("tiempo", "ventas de los ultimos 3 dias", periodo="ultimos", dias=3, metrica="monto")
semilla("tiempo", "pedidos de las ultimas 2 semanas", periodo="ultimos", dias=14)
semilla("tiempo", "ventas de los ultimos 2 meses", periodo="ultimos", dias=60, metrica="monto")


# ------------------------------------------------------------------ generacion de variantes
def generar(minimo: int, semilla_azar: int, dim: pd.DataFrame, clientes_ok: list[str]) -> list[dict]:
    r = random.Random(semilla_azar)
    seqs = [str(x) for x in dim["Sequence"].head(400)]
    vistos, out = set(), []
    for n_sem, (rol, pl, esp) in enumerate(S, 1):
        usa_periodo = "{P}" in pl or "{D}" in pl
        # cada semilla produce hasta 6 variantes distintas; las que tienen ranuras, mas
        intentos = 0
        hechas = 0
        meta = 6 if (usa_periodo or any(k in pl for k in ("{C}", "{PR}", "{K}", "{B}", "{SEQ}"))) else 3
        while hechas < meta and intentos < 60:
            intentos += 1
            ex = dict(esp)
            q = pl
            nombres = []
            if "{P}" in q or "{D}" in q:
                a, de, imp = r.choice(PERIODOS)
                q = q.replace("{P}", a).replace("{D}", de)
                ex.update({k: v for k, v in imp.items() if k not in ex or ex[k] is None})
                if esp.get("periodo", "?") is None:
                    ex.pop("periodo", None)
            if "{C}" in q:
                c = r.choice(clientes_ok)
                q = q.replace("{C}", c)
                if "{C2}" in q:
                    c2 = r.choice([x for x in clientes_ok if x != c])
                    q = q.replace("{C2}", c2)
                    ex["clientes_ambos"] = {c, c2}
                ex = {k: ([c] if v == ["{C}"] else v) for k, v in ex.items()}
            if "{PR}" in q:
                p = r.choice(PRODUCTOS)
                nombres.append(p)
                q = q.replace("{PR}", errata(p, r) if (r.random() < .12 and " " not in p) else p)
            if "{K}" in q:
                q = q.replace("{K}", r.choice(CLASIF))
            if "{B}" in q:
                txt, canon = r.choice(BODEGAS)
                q = q.replace("{B}", txt)
                ex = {k: ([canon] if v == ["{BE}"] else v) for k, v in ex.items()}
            if "{SEQ}" in q:
                q = q.replace("{SEQ}", r.choice(seqs))
            q = r.choice(PREFIJOS) + q + r.choice(SUFIJOS)
            q = ruido_texto(q, r)
            if r.random() < .25:
                q = sin_tilde(q)
            q = re.sub(r"\s+", " ", q).strip()
            if q.lower() in vistos:
                continue
            vistos.add(q.lower())
            out.append({"id": len(out) + 1, "semilla": n_sem, "ronda": 2 if n_sem > RONDA2 else 1, "rol": rol, "plantilla": pl, "pregunta": q, "esperado": ex})
            hechas += 1
    r.shuffle(out)
    return out


# ------------------------------------------------------------------ evaluacion
def verifica(plan: dict | None, res: dict, esp: dict, hoy: pd.Timestamp) -> list[str]:
    """-> lista de diferencias entre lo que se esperaba y lo que entendio el asistente (vacia = bien)."""
    if plan is None:
        return ["no entendio la pregunta"]
    malos = []
    for k, v in esp.items():
        if k == "clientes_ambos":
            if set(plan["cliente"]) != set(v):
                malos.append(f"clientes {plan['cliente']} != {sorted(v)}")
        elif k == "producto":
            if v and not (plan["producto"] or plan["sku"]):
                malos.append("no reconocio el producto")
        elif k in ("estado",):
            if not set(v) <= set(plan["estado"]):
                malos.append(f"estado {plan['estado']} no incluye {v}")
        elif k in ("cliente", "bodega"):
            if set(plan[k]) != set(v):
                malos.append(f"{k} {plan[k]} != {v}")
        elif k == "desde":
            if plan["desde"] != v:
                malos.append(f"desde {plan['desde']} != {v}")
        elif k == "hasta":
            if plan["hasta"] != v:
                malos.append(f"hasta {plan['hasta']} != {v}")
        elif k == "top":
            if plan["top"] != v:
                malos.append(f"top {plan['top']} != {v}")
        elif plan.get(k) != v:
            malos.append(f"{k} {plan.get(k)!r} != {v!r}")
    return malos


def rango_esperado(esp: dict, hoy: pd.Timestamp):
    """Fechas de cada periodo calculadas aparte del asistente (verdad independiente)."""
    p = esp.get("periodo") or "mes"
    d = pd.Timedelta(days=1)
    if p == "hoy":
        return hoy, hoy
    if p == "ayer":
        return hoy - d, hoy - d
    if p == "semana":
        return hoy - pd.Timedelta(days=hoy.weekday()), hoy
    if p == "semana_anterior":
        ini = hoy - pd.Timedelta(days=hoy.weekday() + 7)
        return ini, ini + pd.Timedelta(days=6)
    if p == "mes":
        return hoy.replace(day=1), hoy
    if p == "mes_anterior":
        fin = hoy.replace(day=1) - d
        return fin.replace(day=1), fin
    if p == "ultimos":
        return hoy - pd.Timedelta(days=esp["dias"] - 1), hoy
    if p == "rango":
        return pd.Timestamp(esp["desde"]), pd.Timestamp(esp.get("hasta") or hoy)
    return None


def valor_esperado(esp: dict, dim: pd.DataFrame, hoy: pd.Timestamp):
    """Calcula directo sobre los datos la cifra de las preguntas simples (una metrica, filtros basicos). None si no aplica."""
    m = esp.get("metrica")
    if m not in ("pedidos", "monto", "unidades", "ticket") or esp.get("accion") not in (None, "medir") or any(k in esp for k in ("agrupar", "producto", "comparar", "top", "orden", "monto_min", "monto_max", "edad_min", "stock_modo")):
        return None
    if set(esp.get("estado", [])) - {"cancelado", "pendiente", "facturado", "no_integrado", "vencido"}:
        return None
    ini, fin = rango_esperado(esp, hoy)
    d = dim[(dim["Creation_Date"] >= ini) & (dim["Creation_Date"] <= fin)]
    cl = esp.get("cliente") or (list(esp["clientes_ambos"]) if esp.get("clientes_ambos") else None)
    if cl:
        d = d[d["SalesChannelName"].isin(cl)]
    if esp.get("bodega"):
        d = d[d["warehouse"].isin(esp["bodega"])]
    est = esp.get("estado", [])
    if "cancelado" not in est:
        d = d[d["Status"] != "canceled"]
    for e in est:
        d = d[{"cancelado": d["Status"] == "canceled", "pendiente": d["Status"] == "ready-for-handling", "facturado": d["Status"] == "invoiced",
               "no_integrado": d["Estado Ingreso"] == "No ingresado",
               "vencido": (d["Status"] == "ready-for-handling") & (d["Shipping_Estimate_Date"] < hoy)}[e]]
    if m == "pedidos":
        return float(len(d))
    if m == "unidades":
        return float(d["Unidades"].sum())
    if m == "monto":
        return float(d["Total_Value"].sum())
    return float(d["Total_Value"].sum() / len(d)) if len(d) else None


def correr(minimo: int, semilla_azar: int):
    memoria.reiniciar_para_pruebas(str(Path(os.environ.get("TMPDIR", "/tmp")) / "sim_hist.jsonl"))
    dim, hoy = servicio.base_pedidos()
    clientes_ok = [c for c in CLIENTES if c in set(dim["SalesChannelName"])]
    preguntas = generar(minimo, semilla_azar, dim, clientes_ok)
    filas = []
    for it in preguntas:
        motor._LLAMADAS.clear()
        try:
            res = responder(it["pregunta"])
            err = None
        except Exception as e:  # noqa: BLE001
            res, err = {"ok": False, "texto": ""}, f"EXCEPCION {e!r}"[:120]
        plan = res.get("plan") if (res.get("ok") or res.get("ayuda")) else None
        dif = verifica(plan, res, it["esperado"], hoy) if not err else [err]
        texto = res.get("texto") or ""
        ve = valor_esperado(it["esperado"], dim, hoy) if not dif else None
        if ve is not None and res.get("valor") is not None and abs(float(res["valor"]) - ve) > max(1.0, abs(ve) * 1e-9):
            dif = dif + [f"valor {res['valor']} != {ve} (calculo directo)"]
        elif ve is not None and res.get("valor") is None:
            dif = dif + ["sin valor para comparar"]
        ruido = any("No usé estas palabras" in n for n in res.get("notas", []))
        filas.append({**it, "ok": bool(res.get("ok")), "tipo": res.get("tipo"), "respuesta": texto, "diferencias": dif, "ruido": ruido,
                      "notas": " | ".join(res.get("notas", []))[:300], "plan": plan, "verificada_cifra": ve is not None})
    return filas, hoy


def informe(filas: list[dict], hoy) -> str:
    n = len(filas)
    ent = sum(not f["diferencias"] for f in filas)
    resp = sum(f["ok"] and bool(f["respuesta"]) for f in filas)
    por_rol = defaultdict(lambda: [0, 0])
    for f in filas:
        por_rol[f["rol"]][0] += 1
        por_rol[f["rol"]][1] += not f["diferencias"]
    fallos = [f for f in filas if f["diferencias"]]
    por_sem = Counter((f["plantilla"]) for f in fallos)
    tipos = Counter(f["tipo"] for f in filas)
    L = ["# Simulación de analistas: informe", "", f"- Semillas (preguntas base de los analistas): **{len(S)}**",
         f"- Preguntas distintas generadas y respondidas: **{n}**", f"- Fecha de los datos de ejemplo: {hoy.strftime('%d-%m-%Y')}",
         f"- El asistente entendió lo esperado: **{ent}/{n} ({100 * ent / n:.1f}%)**", f"- Respondió con texto y sin error: **{resp}/{n} ({100 * resp / n:.1f}%)**",
         f"- Cifras verificadas contra un cálculo directo: **{sum(f['verificada_cifra'] for f in filas)}** preguntas, "
         f"{sum(f['verificada_cifra'] and not f['diferencias'] for f in filas)} coinciden",
         f"- Respuestas con palabras ignoradas (ruido): {sum(f['ruido'] for f in filas)}", "", "## Por analista", "", "| Rol | Preguntas | Entendidas | % |", "|---|---:|---:|---:|"]
    for rol, (a, b) in sorted(por_rol.items()):
        L.append(f"| {rol} | {a} | {b} | {100 * b / a:.0f}% |")
    for ronda in (1, 2):
        fr = [f for f in filas if f["ronda"] == ronda]
        if fr:
            L.append(f"- Ronda {ronda} ({'preguntas base de los analistas' if ronda == 1 else 'redacción coloquial a ciegas'}): "
                     f"{sum(not f['diferencias'] for f in fr)}/{len(fr)} entendidas ({100 * sum(not f['diferencias'] for f in fr) / len(fr):.1f}%)")
    L += ["", "## Tipos de respuesta", "", ", ".join(f"{k}: {v}" for k, v in tipos.most_common()), "", "## Plantillas con fallas", ""]
    if not fallos:
        L.append("Ninguna.")
    for pl, c in por_sem.most_common(25):
        ej = next(f for f in fallos if f["plantilla"] == pl)
        L.append(f"- `{pl}` ({c}): ej. «{ej['pregunta']}» → {'; '.join(ej['diferencias'])}")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minimo", type=int, default=500)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--umbral", type=float, default=.95)
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--ver-fallas", type=int, default=0, help="muestra N preguntas con fallas")
    a = ap.parse_args()
    filas, hoy = correr(a.minimo, a.semilla)
    txt = informe(filas, hoy)
    print(txt)
    if a.ver_fallas:
        for f in [x for x in filas if x["diferencias"]][:a.ver_fallas]:
            print(f"- [{f['rol']}] «{f['pregunta']}» -> {f['diferencias']} | {f['respuesta'][:100]}")
    if a.escribir:
        SALIDA.mkdir(exist_ok=True)
        with (SALIDA / "preguntas_semilla.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["id", "analista", "plantilla", "intencion_esperada"])
            for i, (rol, pl, esp) in enumerate(S, 1):
                w.writerow([i, rol, pl, ", ".join(f"{k}={v}" for k, v in esp.items())])
        with (SALIDA / "respuestas.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["id", "semilla", "analista", "pregunta", "entendio_lo_esperado", "tipo_respuesta", "respuesta", "diferencias", "notas"])
            for f in sorted(filas, key=lambda x: (x["semilla"], x["id"])):
                w.writerow([f["id"], f["semilla"], f["rol"], f["pregunta"], "si" if not f["diferencias"] else "no", f["tipo"] or "", f["respuesta"],
                            "; ".join(f["diferencias"]), f["notas"]])
        (SALIDA / "INFORME.md").write_text(txt, encoding="utf-8")
        print("Escrito en", SALIDA)
    ent = sum(not f["diferencias"] for f in filas) / len(filas)
    if len(filas) < a.minimo:
        print(f"Solo se generaron {len(filas)} preguntas (minimo {a.minimo}).")
        return 1
    return 0 if ent >= a.umbral else 1


if __name__ == "__main__":
    sys.exit(main())
