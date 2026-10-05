"""Planificador por reglas: convierte una pregunta en espanol en un plan (ver esquema.py). Sin IA, sin internet."""
from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

from . import lexico as L
from .catalogo import es_modelo
from .esquema import ALIAS_BODEGA, ALIAS_CLIENTE, conocidos, plan_vacio, validar
from .texto import Texto, tokens

ISO = "%Y-%m-%d"


def _dia(d) -> str:
    return pd.Timestamp(d).strftime(ISO)


def _periodo(X: Texto, hoy: pd.Timestamp) -> dict:
    p: dict = {}
    t = X.t
    if (m := X.buscar(r"(?:ultim\w+|pasad\w+)\s+(\d{1,3})\s+(dias?|semanas?|meses)")):
        n = int(m.group(1)) * {"d": 1, "s": 7, "m": 30}[m.group(2)[0]]
        p.update(periodo="ultimos", dias=max(1, min(n, 400)))
    elif X.buscar(r"semana\s+(pasada|anterior)"):
        p["periodo"] = "semana_anterior"
    elif X.buscar(r"mes\s+(pasado|anterior)"):
        p["periodo"] = "mes_anterior"
    elif X.buscar(r"ultimo mes|mes ultimo"):
        p.update(periodo="ultimos", dias=30)                       # "el ultimo mes" = los ultimos 30 dias (se dice en la respuesta)
    elif X.buscar(r"ultima semana"):
        p.update(periodo="ultimos", dias=7)
    elif X.buscar(r"\banteayer\b"):
        d = _dia(hoy - timedelta(days=2))
        p.update(periodo="rango", desde=d, hasta=d)
    elif (m := X.buscar(r"hace\s+(\d{1,3})\s+dias?")):
        d = _dia(hoy - timedelta(days=int(m.group(1))))
        p.update(periodo="rango", desde=d, hasta=d)
    elif X.buscar(r"\bhoy\b"):
        p["periodo"] = "hoy"
    elif X.buscar(r"\bayer\b"):
        p["periodo"] = "ayer"
    elif X.buscar(r"(?:esta|la)\s+semana|semanal"):
        p["periodo"] = "semana"
    elif X.buscar(r"(?:este|el)\s+mes|mensual|mes en curso"):
        p["periodo"] = "mes"
    elif X.buscar(r"todo el periodo|historic\w*|desde siempre|en total|(?:este|el|todo el)\s+ano"):
        p["periodo"] = "todo"
    fechas = []
    for d, mm, a in re.findall(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b", t):
        try:
            anio = int(a) if a else hoy.year
            anio += 2000 if anio < 100 else 0
            fechas.append(pd.Timestamp(anio, int(mm), int(d)))
        except ValueError:
            pass
    for a, mm, d in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", t):
        try:
            fechas.append(pd.Timestamp(int(a), int(mm), int(d)))
        except ValueError:
            pass
    if fechas:
        fechas = sorted(set(fechas))
        p.update(periodo="rango", desde=_dia(fechas[0]), hasta=_dia(fechas[-1]))
        for i, (tok, _, _) in enumerate(X.tok):
            if re.fullmatch(r"\d{1,4}", tok) and not X.usado[i]:
                X.usado[i] = True
    elif "periodo" not in p:
        for nom in L.MESES:
            if nom in X.todos():
                mes = L.NUM_MES[nom]
                ini = pd.Timestamp(hoy.year if mes <= hoy.month else hoy.year - 1, mes, 1)
                p.update(periodo="rango", desde=_dia(ini), hasta=_dia(ini + pd.offsets.MonthEnd(0)))
                X.marcar_tokens({nom})
                break
    return p


def _entidades(X: Texto, K: dict, plan: dict) -> None:
    libres = lambda: {t for t, u in zip(X.todos(), X.usado) if not u}  # noqa: E731
    for sla in sorted(K["sla"], key=lambda s: -len(tokens(s))):        # SLA primero: "MELI Bluexpress" no es el cliente MELI
        ts = set(tokens(sla))
        if ts and ts <= libres() and (len(ts) > 1 or len(next(iter(ts))) >= 5):
            plan["sla"].append(sla)
            X.marcar_tokens(ts)
    for cl in K["cliente"]:
        ts = set(tokens(cl))
        if ts and ts <= libres():
            plan["cliente"].append(cl)
            X.marcar_tokens(ts)
    for alias, cl in ALIAS_CLIENTE.items():
        if cl in K["cliente"] and cl not in plan["cliente"] and X.buscar(r"\b" + alias + r"\b"):
            plan["cliente"].append(cl)
    for ca in ("BWS", "MKP"):
        if ca in K["canal"] and ca.lower() in libres():
            plan["canal"].append(ca)
            X.marcar_tokens({ca.lower()})
    for b in K["bodega"]:
        ts = set(tokens(b))
        if ts and ts <= libres():
            plan["bodega"].append(b)
            X.marcar_tokens(ts)
    for alias, b in sorted(ALIAS_BODEGA.items(), key=lambda kv: -len(kv[0])):      # "post fechado" antes que "post"
        if b in K["bodega"] and b not in plan["bodega"] and X.buscar(r"\b" + alias.replace("_", " ") + r"s?\b"):
            plan["bodega"].append(b)
    if plan["bodega"]:
        X.marcar_tokens({"fechado"})


def _estados(X: Texto, plan: dict) -> None:
    e = plan["estado"]
    for clave, pat in L.ALERTAS.items():
        if X.buscar(pat):
            e.append(clave)
    if X.buscar(L.P_SIN_DESPACHO):
        e.append("sin_despacho")
    if X.buscar(L.P_NO_INTEGRADO):
        e.append("no_integrado")
    elif X.buscar(L.P_INTEGRADO):
        e.append("integrado")
    if X.buscar(L.P_CANCELADO):
        e.append("cancelado")
    if "sin_despacho" not in e and X.buscar(L.P_FACTURADO):
        e.append("facturado")
    if X.buscar(L.P_PENDIENTE):
        e.append("pendiente")
    if X.buscar(L.P_VENCIDO):
        e.append("vencido")
    if X.buscar(L.P_QUIEBRE):
        e.append("quiebre")


def _agrupacion(X: Texto, plan: dict) -> None:
    if (m := X.buscar(L.P_POR_DIM)):
        plan["agrupar"] = L.DIMENSIONES[m.group(1)]
    elif (m := X.buscar(L.P_CUAL_DIM)):
        plan["agrupar"] = L.DIMENSIONES[m.group(1)]
        plan["orden"] = "asc" if m.group(2) in ("menos", "menor", "peor") else "desc"      # "el dia con mas pedidos": ranking, no cronologia
        if X.hay(r"\b(que|cual)\s+(?:\w+\s+){0,2}?" + m.group(1) + r"\b"):
            plan["top"] = plan["top"] or 1
    elif (m := X.buscar(L.P_STATUS_DE)):
        plan["agrupar"] = "status" if m.group(1) == "status" else "estado"
    elif X.buscar(L.P_RANKING):
        plan["agrupar"] = "cliente" if X.hay(r"\bclientes?\b") else "producto"
        plan["orden"] = "asc" if X.hay(r"menos vendid|peores") else "desc"
    elif X.buscar(r"cada dia|dia a dia|diario"):
        plan["agrupar"] = "dia"
    if (n := X.buscar(r"\btop\s*(\d{1,2})\b|\b(?:los|las|primeros|primeras)\s+(\d{1,3})\b")):
        plan["top"] = max(1, min(int(n.group(1) or n.group(2)), 300))
    if X.buscar(L.P_ASC):
        plan["orden"] = "asc"
    if X.buscar(L.P_COMPARAR):
        plan["comparar"] = True


def _metrica(X: Texto, plan: dict) -> None:
    for clave, pat in L.P_METRICAS:
        if X.buscar(pat):
            plan["metrica"] = clave
            return


def _pedido_o_sku(X: Texto, dim: pd.DataFrame, plan: dict) -> None:
    if not any(t.isdigit() and len(t) >= 6 for t, _, _ in X.tok):
        return                                                    # sin numeros largos no hay pedido ni SKU que buscar
    seqs = set(dim["Sequence"].astype(str))
    sap = {}
    for sq, ps in zip(dim["Sequence"], dim["Pedido SAP"]):
        for n in str(ps).split("|"):
            if n.strip():
                sap[n.strip()] = sq
    for i, (t, _, _) in enumerate(X.tok):
        if not t.isdigit():
            continue
        if len(t) >= 6 and t in seqs:
            plan["pedido"], X.usado[i] = t, True
        elif len(t) >= 6 and t in sap:
            plan["pedido"], X.usado[i] = sap[t], True
        elif len(t) == 9:
            plan["sku"], X.usado[i] = t, True


def planificar(q: str, dim: pd.DataFrame, hoy: pd.Timestamp, previo: dict | None = None, cat_fn=None):
    """-> (plan, banderas). `cat_fn()` entrega el catalogo de productos solo si hace falta (cargar las lineas cuesta)."""
    X, K = Texto(q), conocidos(dim)
    plan, expl = plan_vacio(), set()
    ban = {"ignoradas": [], "correcciones": {}, "entendio": False, "hereda": False}

    _pedido_o_sku(X, dim, plan)
    per = _periodo(X, hoy)
    plan.update(per)
    _estados(X, plan)                         # primero: "alerta BWS" no es el canal BWS, "alerta post" no es la bodega
    _entidades(X, K, plan)
    _agrupacion(X, plan)
    _metrica(X, plan)
    quitar = {"pct_integracion": "integrado", "pct_pendiente": "pendiente"}.get(plan["metrica"])
    if quitar in plan["estado"]:
        plan["estado"].remove(quitar)         # en "% pendiente" la palabra es la medida, no un filtro

    for k in ("pedido", "sku"):
        if plan[k]:
            expl.add("pedido" if k == "pedido" else "producto")
    if per:
        expl.add("periodo")
    for k in ("sla", "cliente", "canal", "bodega", "estado", "agrupar", "metrica", "top", "orden"):
        if plan[k]:
            expl.add(k)
    if plan["comparar"]:
        expl.add("comparar")

    # lo que sobra puede ser el nombre de un producto
    libres = [t for t in X.libres() if t not in L.STOP and t not in L.MESES and len(t) >= 2 and not (t.isdigit() and len(t) < 2)]
    if libres and not plan["pedido"]:
        cat = cat_fn() if cat_fn else None
        if cat is not None:
            prod, corr, ign, desconocidos = cat.reconocer(libres)
            ban.update(correcciones=corr, ignoradas=ign)
            libres = prod + desconocidos
        else:
            libres = [t for t in libres if t not in L.STOP]
        if libres:
            plan["producto"] = " ".join(libres)
            expl.add("producto")

    # accion
    stock_cue = X.hay(L.P_STOCK) and not X.hay(r"\b(pedidos?|ordenes)\b")
    listar = X.hay(L.P_LISTAR) and X.hay(L.P_ENTIDAD_LISTA) and not X.hay(L.P_CONTAR) and not plan["agrupar"]
    if X.hay(L.P_AYUDA) or (X.hay(L.P_SALUDO) and not expl):
        plan["accion"] = "ayuda"
    elif X.hay(L.P_INFO):
        plan["accion"] = "info"
    elif plan["pedido"]:
        plan["accion"] = "pedido"
    elif stock_cue:
        plan["accion"] = "stock"
    elif listar or (X.hay(r"\bpedidos?\b|\bordenes\b") and not plan["metrica"] and not plan["agrupar"] and not X.hay(L.P_CONTAR)
                    and ({"estado", "cliente", "bodega", "canal", "sla", "producto"} & expl)):
        plan["accion"] = "listar"
    elif expl:
        plan["accion"] = "medir"
    if plan["accion"]:
        expl.add("accion")
    ban["entendio"] = bool(plan["accion"])

    # seguimiento ("y ayer?", "ver los pedidos", "por cliente"): hereda lo que no se menciona
    propio = {"metrica", "producto", "pedido", "cliente", "canal", "bodega", "sla", "estado"} & expl     # una pregunta con tema propio no hereda
    corto = len(X.tok) <= 8 and not propio and bool(expl)
    if previo and ban["entendio"] and plan["accion"] not in ("ayuda", "info") and (X.t.strip().startswith("y ") or corto):
        base = validar(previo, K)
        for k, v in plan.items():
            if k in ("canal", "cliente", "bodega", "sla", "estado"):
                if v:
                    base[k] = v
            elif k in ("periodo", "dias", "desde", "hasta"):
                if "periodo" in expl:
                    base[k] = v
            elif k == "accion":
                if v and (v != "medir" or "agrupar" in expl or "metrica" in expl or base[k] == "stock"):
                    base[k] = v
            elif k == "comparar":
                base[k] = base[k] or v
            elif v not in (None, [], False) and k in expl:
                base[k] = v
        plan = base
        ban["hereda"] = True
    return plan, ban
