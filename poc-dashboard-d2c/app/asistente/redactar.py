"""Redaccion de la respuesta en espanol: frase principal, desglose y preguntas de seguimiento."""
from __future__ import annotations

from .texto import lista_es, sa

ADJ = {"no_integrado": "no integrados", "integrado": "integrados", "cancelado": "cancelados", "pendiente": "pendientes",
       "facturado": "facturados", "vencido": "con entrega vencida", "sin_despacho": "facturados sin despacho",
       "alerta_bws": "con alerta BWS", "alerta_post": "con alerta POST Fechado", "alerta_mkp": "con alerta MKP",
       "quiebre": "pendientes por quiebre de stock"}
EJEMPLOS = ["¿Cuál es la venta de los últimos 7 días del MED165B?",
            "¿Cuántos pedidos se cancelaron el último mes?",
            "Pedidos de POST Fechado hoy con productos, cantidad y monto",
            "¿Cuál es el status de POST Fechado hoy?",
            "¿Hay stock del refrigerador MED 165B?",
            "Top 5 clientes por monto este mes",
            "¿Qué debo revisar hoy?",
            "¿Cómo vamos este mes?",
            "Ventas por clasificación",
            "Los 10 pedidos más caros"]


DIM_SING = {"cliente": "cliente", "dia": "día", "sla": "SLA", "producto": "producto", "canal": "canal", "bodega": "bodega", "mes": "mes",
            "semana": "semana", "clasif2": "grupo de productos"}


def num(v, f: str = "n") -> str:
    if v is None:
        return "sin dato"
    if f == "pct":
        return f"{v * 100:.1f}%".replace(".", ",")
    if f == "dias":
        return f"{v:.1f} días".replace(".", ",")
    if f == "n1":
        return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
            f0 = res["tabla"]["filas"][0]
            if f0[4] is None:
                return f"{res['productos'][0]['descripcion']} (código SAP {f0[0]}) no aparece en la tabla de stock VTEX."
            return f"{base} de {res['productos'][0]['descripcion']} (código SAP {f0[0]})."
        filas = res["tabla"]["filas"] if res["productos"] else []
        sin = [f[1] for f in filas if f[4] is not None and f[4] <= 0]
        sd = [f[1] for f in filas if f[4] is None]
        return (base + (f" entre {len(res['productos'])} productos" if res["productos"] else "") + "." + (f" Sin stock: {lista_es(sin)}." if sin else "")
                + (f" Sin dato en la tabla de stock: {lista_es(sd)}." if sd else ""))
    if res["tipo"] == "lista" and plan["metrica"] == "monto" and plan["orden"] and res.get("tabla") and res["tabla"]["filas"]:       # "los 10 pedidos mas caros"
        t0 = res["tabla"]
        i = next((k for k, c in enumerate(t0["cols"]) if c["n"] == "Monto"), 1)
        ic = next((k for k, c in enumerate(t0["cols"]) if c["n"] == "Cliente"), None)
        top = ", ".join(f"{f[0]} ({num(f[i], '$')}" + (f", {f[ic]}" if ic is not None else "") + ")" for f in t0["filas"][:3])
        return (f"{et}: {'el pedido' if len(t0['filas']) == 1 else 'los pedidos'} de {'mayor' if plan['orden'] == 'desc' else 'menor'} monto{donde}: {top}"
                + (" y más (ver la tabla)." if len(t0["filas"]) > 3 else "."))
    if res["tipo"] == "lista":
        n = res.get("total_filas", 0)
        if not res["resumen"]["pedidos"]:
            return f"{et}: no hay pedidos{(' ' + adjs) if adjs else ''}{donde} con esos criterios."
        r = res["resumen"]
        prod = f" de {res['productos'][0]['descripcion']}" if res["productos"] else ""
        return (f"{et}: {num(r['pedidos'])} pedido{'s' if r['pedidos'] != 1 else ''}{(' ' + adjs) if adjs else ''}{donde}{prod}, "
                f"{num(r['unidades'])} unidades, {num(r['monto'], '$')}.")
    t0 = res.get("tabla")
    if res["tipo"] == "lista" and plan["metrica"] == "monto" and plan["orden"] and t0 and t0["filas"]:     # "los 10 pedidos mas caros"
        i = next((k for k, c in enumerate(t0["cols"]) if c["n"] == "Monto"), 1)
        top = ", ".join(f"{f[0]} ({num(f[i], '$')}, {f[-2] if res.get('con_lineas') else f[4]})" for f in t0["filas"][:3])
        return f"{et}: {'los pedidos de mayor monto' if plan['orden'] == 'desc' else 'los pedidos de menor monto'}{donde} son {top}" + (" y más (ver la tabla)." if len(t0["filas"]) > 3 else ".")
    if res["tipo"] == "tabla" and t0 and t0["filas"] and plan["top"] == 1 and plan["agrupar"] in DIM_SING and plan["orden"]:
        nombre = {"pedidos": "pedidos", "unidades": "unidades", "monto": "ventas", "lineas": "líneas", "ticket": "ticket"}.get(m, "pedidos")
        col = {"pedidos": "Pedidos", "unidades": "Unidades", "monto": "Monto", "lineas": "Líneas", "ticket": "Ticket"}.get(m, "Pedidos")
        i = next((k for k, c in enumerate(t0["cols"]) if c["n"] == col), 1)
        f0 = t0["filas"][0]
        return (f"{et}: el {DIM_SING[plan['agrupar']]} con {'más' if plan['orden'] == 'desc' else 'menos'} {nombre}{(' ' + adjs) if adjs else ''}{donde} es "
                f"{f0[0]} ({num(f0[i], t0['cols'][i]['f'])}).")
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
    crono = plan["agrupar"] in ("dia", "semana", "mes") and not plan["orden"]
    if res["tipo"] == "tabla" and t and t["filas"] and crono and len(t["filas"]) > 1:        # evolucion: el maximo y el minimo, el detalle va en la tabla
        nombre = {"pedidos": "Pedidos", "unidades": "Unidades", "monto": "Monto", "lineas": "Líneas", "ticket": "Ticket"}.get(m)
        i = next((k for k, c in enumerate(t["cols"]) if c["n"] == nombre), 1)
        con = [f for f in t["filas"] if f[i] is not None]
        if con:
            mx, mn = max(con, key=lambda f: f[i]), min(con, key=lambda f: f[i])
            txt += f" Máximo: {mx[0]} ({num(mx[i], t['cols'][i]['f'])}); mínimo: {mn[0]} ({num(mn[i], t['cols'][i]['f'])}); {len(t['filas'])} períodos en la tabla."
    if res["tipo"] == "tabla" and t and t["filas"] and not crono:
        nombre = {"pedidos": "Pedidos", "unidades": "Unidades", "monto": "Monto", "lineas": "Líneas", "ticket": "Ticket"}.get(m)
        i = next((k for k, c in enumerate(t["cols"]) if c["n"] == nombre), 1)
        visibles = t["filas"] if len(t["filas"]) <= 8 else t["filas"][:3]
        txt += " " + ", ".join(f"{fl[0]}: {num(fl[i], t['cols'][i]['f'])}" for fl in visibles) + ("." if len(t["filas"]) <= 8 else f" y {res.get('total_filas', len(t['filas'])) - len(visibles)} más (ver la tabla).")
    c = res.get("comparacion")
    if c:
        signo = "+" if c["delta"] >= 0 else "−"
        pct = f" ({signo}{abs(c['pct']) * 100:.1f}%)".replace(".", ",") if c["pct"] is not None else ""
        txt += f" Frente al período anterior ({c['etiqueta']}): {num(c['anterior'], f if m not in ('pedidos', 'unidades', 'lineas') else 'n')}, {signo}{num(abs(c['delta']), f if m not in ('pedidos', 'unidades', 'lineas') else 'n')}{pct}."
    return txt


def seguimientos(res: dict, plan: dict, vistas: list | None = None) -> list[str]:
    """Hasta 3 preguntas de seguimiento utiles para ESTA respuesta, sin repetir las que ya se hicieron en la conversacion."""
    acc, g = plan.get("accion") or "medir", plan.get("agrupar")
    vistas = {sa(v) for v in (vistas or [])}
    if res.get("tipo") == "alertas":
        pool = ["productos con poco stock", "pedidos con entrega vencida", "pedidos no integrados", "¿cómo vamos este mes?", "pedidos facturados sin despacho"]
    elif res.get("tipo") == "resumen":
        pool = ["¿hay algo raro hoy?", "ventas por clasificación", "top 5 clientes por monto", "ventas por día", "stock total"]
    elif res.get("tipo") == "stock":
        pool = ["productos con poco stock", "cobertura de stock", "¿qué productos no tienen stock?", "productos sin ventas", "y las unidades vendidas hoy", "y los pedidos pendientes"]
    elif res.get("tipo") == "sin_ventas":
        pool = ["stock total", "ventas por clasificación", "top 5 productos más vendidos"]
    elif acc == "listar":
        pool = ["Resumen por status", "Por cliente", "Comparar con el período anterior", "Por bodega", "Exportar: ver los pedidos más caros"]
    elif g:
        pool = ["Ver los pedidos", "Por día" if g != "dia" else "Por cliente", "Comparar con el período anterior", "Por canal" if g != "canal" else "Por bodega",
                "Por clasificación" if g != "clasif2" else "Por cliente", "solo los cancelados", "Ticket promedio"]
    else:
        pool = ["Por día", "Por cliente", "Ver los pedidos", "Comparar con el período anterior", "Por clasificación", "Por bodega", "% de cancelación"]
        if plan.get("producto") or plan.get("sku"):
            pool = ["Ver los pedidos", "Por día", "y el stock", "Por cliente", "Comparar con el período anterior"]
    if plan.get("comparar"):
        pool = [x for x in pool if "Comparar" not in x]
    nuevos = [x for x in pool if sa(x) not in vistas]
    return (nuevos or pool)[:3]


def ayuda(saludo: bool) -> tuple[str, list[str]]:
    t = ("Hola, soy el asistente del tablero. " if saludo else "") + (
        "Respondo con los datos de VTEX y SAP que ya están cargados: pedidos (estado, status, canal, cliente, bodega, SLA, montos, "
        "fechas), las líneas de cada pedido (producto, código SAP, cantidad, precio), el cruce con SAP (pedido SAP, facturado sin "
        "despacho) y el stock VTEX. Puedo contar, sumar, listar, desglosar por día, cliente, bodega, status o producto, "
        "comparar períodos y buscar un pedido por su número. No tengo costos, márgenes ni datos de clientes finales.")
    return t, EJEMPLOS
