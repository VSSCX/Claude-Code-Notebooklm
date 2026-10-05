"""Redaccion de la respuesta en espanol: frase principal, desglose y preguntas de seguimiento."""
from __future__ import annotations

from .texto import lista_es

ADJ = {"no_integrado": "no integrados", "integrado": "integrados", "cancelado": "cancelados", "pendiente": "pendientes",
       "facturado": "facturados", "vencido": "con entrega vencida", "sin_despacho": "facturados sin despacho",
       "alerta_bws": "con alerta BWS", "alerta_post": "con alerta POST Fechado", "alerta_mkp": "con alerta MKP",
       "quiebre": "pendientes por quiebre de stock"}
EJEMPLOS = ["¿Cuál es la venta de los últimos 7 días del MED165B?",
            "¿Cuántos pedidos se cancelaron el último mes?",
            "Pedidos de POST Fechado hoy con productos, cantidad y monto",
            "¿Cuál es el status de POST Fechado hoy?",
            "¿Hay stock del refrigerador MED 165B?",
            "Top 5 clientes por monto este mes"]


def num(v, f: str = "n") -> str:
    if v is None:
        return "sin dato"
    if f == "pct":
        return f"{v * 100:.1f}%".replace(".", ",")
    if f == "dias":
        return f"{v:.1f} días".replace(".", ",")
    s = f"{v:,.0f}".replace(",", ".")
    return "$" + s if f == "$" else s


def _donde(plan: dict) -> str:
    p = []
    if plan["cliente"]:
        p.append("de " + lista_es(plan["cliente"]))
    if plan["canal"]:
        p.append("del canal " + lista_es(plan["canal"]))
    if plan["bodega"]:
        p.append("en la bodega " + lista_es(plan["bodega"]))
    if plan["sla"]:
        p.append("con SLA " + lista_es(plan["sla"]))
    return (" " + " ".join(p)) if p else ""


def frase(res: dict, plan: dict, dim) -> str:
    m, v = res["metrica"], res.get("valor")
    et = res["etiqueta"]
    adjs = " y ".join(ADJ[e] for e in plan["estado"])
    donde = _donde(plan)
    if res["tipo"] == "stock":
        base = f"{num(v)} {res['unidad']}"
        if res["productos"] and len(res["productos"]) == 1:
            return f"{base} de {res['productos'][0]['descripcion']}."
        sin = [f[1] for f in res["tabla"]["filas"] if f[4] <= 0] if res["productos"] else []
        return base + (f" entre {len(res['productos'])} productos" if res["productos"] else "") + "." + (f" Sin stock: {lista_es(sin)}." if sin else "")
    if res["tipo"] == "lista":
        n = res.get("total_filas", 0)
        if not res["resumen"]["pedidos"]:
            return f"{et}: no hay pedidos{(' ' + adjs) if adjs else ''}{donde} con esos criterios."
        r = res["resumen"]
        prod = f" de {res['productos'][0]['descripcion']}" if res["productos"] else ""
        return (f"{et}: {num(r['pedidos'])} pedido{'s' if r['pedidos'] != 1 else ''}{(' ' + adjs) if adjs else ''}{donde}{prod}, "
                f"{num(r['unidades'])} unidades, {num(r['monto'], '$')}.")
    prod = ""
    if res["productos"]:
        n = len(res["productos"])
        prod = f" de {res['productos'][0]['descripcion']}" + (f" y {n - 1} variante{'s' if n > 2 else ''} parecida{'s' if n > 2 else ''}" if n > 1 else "")
    if v in (None, 0) and m not in ("pct_integracion", "pct_pendiente", "antiguedad", "monto_riesgo", "desfase"):
        ult = dim["Creation_Date"].max()
        extra = f" El último pedido cargado es del {ult.strftime('%d-%m-%Y')}." if et.startswith(("Hoy", "Ayer")) else ""
        return f"{et}: no hay {'unidades' if m == 'unidades' else 'registros'}{(' ' + adjs) if adjs else ''}{prod}{donde} con esos criterios.{extra}"
    f = res["formato"]
    if m == "pedidos":
        suj = f"{num(v)} pedido{'s' if v != 1 else ''}{(' ' + adjs) if adjs else ''}{prod}"
    elif m == "monto":
        suj = f"{num(v, '$')}{prod if prod else ' en ventas'}" + (f" (pedidos {adjs})" if adjs else "")
    elif m == "unidades":
        suj = f"{num(v)} unidades{prod}" + (f" en pedidos {adjs}" if adjs else "")
    elif m == "lineas":
        suj = f"{num(v)} líneas{prod}" + (f" en pedidos {adjs}" if adjs else "")
    else:
        suj = f"{num(v, f)} {res['unidad']}"
    txt = f"{et}: {suj}{donde}"
    r = res["resumen"]
    if m in ("unidades", "monto", "lineas") and r and r["pedidos"]:
        txt += f", en {num(r['pedidos'])} pedido{'s' if r['pedidos'] != 1 else ''}"
    txt += "."
    t = res.get("tabla")
    if res["tipo"] == "tabla" and t and t["filas"] and (len(t["filas"]) <= 8 or plan["orden"]) and (plan["agrupar"] not in ("dia", "semana", "mes") or plan["orden"]):
        nombre = {"pedidos": "Pedidos", "unidades": "Unidades", "monto": "Monto", "lineas": "Líneas", "ticket": "Ticket"}.get(m)
        i = next((k for k, c in enumerate(t["cols"]) if c["n"] == nombre), 1)
        visibles = t["filas"] if len(t["filas"]) <= 8 else t["filas"][:3]
        txt += " " + ", ".join(f"{fl[0]}: {num(fl[i], t['cols'][i]['f'])}" for fl in visibles) + "."
    c = res.get("comparacion")
    if c:
        signo = "+" if c["delta"] >= 0 else "−"
        pct = f" ({signo}{abs(c['pct']) * 100:.1f}%)".replace(".", ",") if c["pct"] is not None else ""
        txt += f" Frente al período anterior ({c['etiqueta']}): {num(c['anterior'], f if m not in ('pedidos', 'unidades', 'lineas') else 'n')}, {signo}{num(abs(c['delta']), f if m not in ('pedidos', 'unidades', 'lineas') else 'n')}{pct}."
    return txt


def seguimientos(res: dict, plan: dict) -> list[str]:
    acc, g = plan.get("accion") or "medir", plan.get("agrupar")
    if res.get("tipo") == "stock":
        return ["y las unidades vendidas hoy", "y los pedidos pendientes"]
    if acc == "listar":
        s = ["Resumen por status", "Por cliente", "Comparar con el período anterior"]
    elif g:
        s = ["Ver los pedidos"] + (["Por día"] if g != "dia" else ["Por cliente"]) + ["Comparar con el período anterior"]
    else:
        s = ["Por día", "Por cliente", "Ver los pedidos"]
        if plan.get("producto") or plan.get("sku"):
            s = ["Ver los pedidos", "Por día", "y el stock"]
    return s[:3]


def ayuda(saludo: bool) -> tuple[str, list[str]]:
    t = ("Hola, soy el asistente del tablero. " if saludo else "") + (
        "Respondo con los datos de VTEX y SAP que ya están cargados: pedidos (estado, status, canal, cliente, bodega, SLA, montos, "
        "fechas), las líneas de cada pedido (producto, código SAP, cantidad, precio), el cruce con SAP (pedido SAP, facturado sin "
        "despacho) y el stock VTEX. Puedo contar, sumar, listar, desglosar por día, cliente, bodega, status o producto, "
        "comparar períodos y buscar un pedido por su número. No tengo costos, márgenes ni datos de clientes finales.")
    return t, EJEMPLOS
