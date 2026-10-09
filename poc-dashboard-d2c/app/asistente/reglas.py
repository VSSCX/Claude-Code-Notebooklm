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


DIAS_SEM = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
_MES_RE = "|".join(L.MESES)


def _fecha_dm(d, mes, a, hoy):
    m = L.NUM_MES[mes]
    y = int(a) if a else (hoy.year if m <= hoy.month else hoy.year - 1)
    return pd.Timestamp(y, m, int(d))


def _periodo(X: Texto, hoy: pd.Timestamp, avisos: list | None = None) -> dict:
    p: dict = {}
    t = X.t
    # --- fechas con dia y mes escritos: "del 5 de agosto", "entre el 1 y el 10 de agosto", "del 15 de julio al 20 de julio"
    try:
        if (m := X.buscar(rf"\b(?:entre|del|desde|de)\s+(?:el\s+)?(\d{{1,2}})(?:\s+de\s+({_MES_RE}))?\s+(?:y|al|a|hasta)\s+(?:el\s+)?(\d{{1,2}})\s+de\s+({_MES_RE})(?:\s+(?:de|del)\s+(\d{{4}}))?\b")):
            d1, m1, d2, m2, a = m.groups()
            a_, b_ = _fecha_dm(d1, m1 or m2, a, hoy), _fecha_dm(d2, m2, a, hoy)
            a_, b_ = min(a_, b_), max(a_, b_)
            return {"periodo": "rango", "desde": _dia(a_), "hasta": _dia(b_)}
        sueltas = []
        while (m := X.buscar(rf"\b(?:el\s+|del\s+|de\s+)?(\d{{1,2}})\s+de\s+({_MES_RE})(?:\s+(?:de|del)\s+(\d{{4}}))?\b")):
            sueltas.append(_fecha_dm(m.group(1), m.group(2), m.group(3), hoy))
            t = X.t = X.t[:m.start()] + " " * (m.end() - m.start()) + X.t[m.end():]            # se consume para no volver a encontrarla
        if sueltas:
            return {"periodo": "rango", "desde": _dia(min(sueltas)), "hasta": _dia(max(sueltas))}
    except ValueError:                                                                         # 31 de febrero, etc.
        if avisos is not None:
            avisos.append("Una de las fechas no existe en el calendario; usé el período por defecto.")
    # --- el dia de la semana: "el lunes", "el viernes pasado"
    if (m := X.buscar(r"\b(?:el\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?:\s+(pasado))?\b")):
        objetivo, pasado = DIAS_SEM[m.group(1)], bool(m.group(2))
        atras = (hoy.weekday() - objetivo) % 7
        if atras == 0 and pasado:
            atras = 7
        d = _dia(hoy - timedelta(days=atras))
        return {"periodo": "rango", "desde": d, "hasta": d}
    # --- relativos
    if (m := X.buscar(r"(?:ultim\w+|pasad\w+)\s+(\d{1,3})\s+(dias?|semanas?|meses)")):
        n = int(m.group(1)) * {"d": 1, "s": 7, "m": 30}[m.group(2)[0]]
        p.update(periodo="ultimos", dias=max(1, min(n, 400)))
    elif X.buscar(r"\b(?:ultimo|ultimos|pasado)\s+trimestre\b|\btrimestre\s+(?:pasado|anterior)\b"):
        p.update(periodo="ultimos", dias=90)
    elif X.buscar(r"\b(?:ultimo|pasado)\s+semestre\b"):
        p.update(periodo="ultimos", dias=180)
    elif X.buscar(r"\bultimo\s+ano\b|\bano\s+(?:pasado|anterior)\b|\bultimos\s+12\s+meses\b"):
        p.update(periodo="ultimos", dias=365)
    elif X.buscar(r"\bsemana\s+(pasada|anterior)\b"):
        p["periodo"] = "semana_anterior"
    elif X.buscar(r"\bmes\s+(pasado|anterior)\b"):
        p["periodo"] = "mes_anterior"
    elif X.buscar(r"\bultimo mes\b|\bmes ultimo\b"):
        p.update(periodo="ultimos", dias=30)                       # "el ultimo mes" = los ultimos 30 dias (se dice en la respuesta)
    elif X.buscar(r"\bultima semana\b"):
        p.update(periodo="ultimos", dias=7)
    elif X.buscar(r"\banteayer\b"):
        d = _dia(hoy - timedelta(days=2))
        p.update(periodo="rango", desde=d, hasta=d)
    elif (m := X.buscar(r"\bhace\s+(\d{1,3})\s+dias?\b")):
        d = _dia(hoy - timedelta(days=int(m.group(1))))
        p.update(periodo="rango", desde=d, hasta=d)
    elif X.hay(r"\b(?:este|del|el|en el)\s+ano\b|\bytd\b|\bacumulado\b|\bdesde enero\b") and X.hay(r"\bhasta hoy\b|\bal dia de hoy\b|\bhasta la fecha\b"):
        X.buscar(r"\b(?:este|del|el|en el)\s+ano\b|\bytd\b|\bacumulado\b|\bdesde enero\b")
        X.buscar(r"\bhasta hoy\b|\bal dia de hoy\b|\bhasta la fecha\b")
        p.update(periodo="rango", desde=_dia(pd.Timestamp(hoy.year, 1, 1)), hasta=_dia(hoy))
    elif X.buscar(r"\bhoy\b"):
        p["periodo"] = "hoy"
    elif X.buscar(r"\bayer\b"):
        p["periodo"] = "ayer"
    elif X.buscar(r"\beste\s+trimestre\b"):
        q0 = pd.Timestamp(hoy.year, 3 * ((hoy.month - 1) // 3) + 1, 1)
        p.update(periodo="rango", desde=_dia(q0), hasta=_dia(hoy))
    elif X.buscar(r"\b(?:este|del|el|en el)\s+ano\b|\bytd\b|\bacumulado\b|\bdesde enero\b"):
        p.update(periodo="rango", desde=_dia(pd.Timestamp(hoy.year, 1, 1)), hasta=_dia(hoy))
    elif X.buscar(r"\b(?:esta|la)\s+semana\b"):
        p["periodo"] = "semana"
    elif X.buscar(r"\btodo el periodo\b|\bhistoric\w*|\bdesde siempre\b|\ben total\b|\btodo el tiempo\b"):
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
            if nom in X.todos():                              # "julio", "ventas de julio", "el mes de julio"
                mes = L.NUM_MES[nom]
                a = re.search(rf"\b{nom}\s+(?:de|del)?\s*(20\d{{2}})\b", t)
                anio = int(a.group(1)) if a else (hoy.year if mes <= hoy.month else hoy.year - 1)
                ini = pd.Timestamp(anio, mes, 1)
                p.update(periodo="rango", desde=_dia(ini), hasta=_dia(ini + pd.offsets.MonthEnd(0)))
                X.marcar_tokens({nom, "mes"})
                if a:
                    X.marcar_tokens({a.group(1)})
                break
        else:
            if X.buscar(r"\b(?:este|el)\s+mes\b|\bmes en curso\b"):
                p["periodo"] = "mes"
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
    elif (m := X.buscar(L.P_SUPER_ANTES)):                               # "el mejor dia", "los peores clientes"
        plan["agrupar"] = L.DIMENSIONES[m.group(2)]
        plan["orden"] = "asc" if m.group(1) in ("peor", "menor") else "desc"
        plan["top"] = plan["top"] or (5 if re.search(r"(?:es|s)$", m.group(0)) else 1)
        plan["_super"] = True
    elif (m := X.buscar(L.P_SUPER_DESPUES)) and L.DIMENSIONES.get(m.group(1)) not in (None,):
        plan["agrupar"] = L.DIMENSIONES[m.group(1)]                    # "cliente con mas cancelaciones", "sla con mas atrasos", "productos con mas pedidos"
        plan["orden"] = "asc" if m.group(2) in ("menos", "menor") else "desc"
        if X.hay(r"\b(?:que|cual|quien)\b") and not X.hay(r"\b(?:" + m.group(1) + r")(?:es|s)\b"):
            plan["top"] = plan["top"] or 1
        plan["_super"] = True
    elif X.buscar(L.P_QUIEN_MAS):
        plan.update(agrupar="cliente", orden="desc", top=plan["top"] or (5 if X.hay(r"\bmejores\b|\bquienes\b") else 1))
        plan["_super"] = True
    elif (m := X.buscar(L.P_LO_MAS_VENDIDO)):
        plan["agrupar"] = "producto"
        plan["orden"] = "asc" if re.search(r"menos|casi no|poco", m.group(0)) else "desc"
        if re.search(r"estrella", m.group(0)):
            plan["top"] = plan["top"] or 5
    elif X.buscar(L.P_EVOLUCION):
        plan["agrupar"] = "dia"
    elif X.buscar(L.P_MENSUAL):
        plan["agrupar"] = "mes"
    elif X.buscar(L.P_SEMANAL):
        plan["agrupar"] = "semana"
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


def _cantidad(n: str, unidad: str | None) -> float:
    v = float(n)
    u = unidad or ""
    if u.startswith("mill") or u == "m":
        return v * 1_000_000
    if u in ("mil", "k"):
        return v * 1_000
    return v


def _numericos(X: Texto, plan: dict) -> None:
    """Filtros por monto ("de mas de 1 millon", "menos de 100 mil") y por antiguedad ("de mas de 2 dias")."""
    if (m := X.buscar(L.P_EDAD)):
        plan["edad_min"] = int(m.group(1))
    if (m := X.buscar(L.P_MONTO_MIN)):
        plan["monto_min"] = _cantidad(m.group(1), m.group(2))
    if (m := X.buscar(L.P_MONTO_MAX)):
        plan["monto_max"] = _cantidad(m.group(1), m.group(2))


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


def planificar(q: str, dim: pd.DataFrame, hoy: pd.Timestamp, previo: dict | None = None, cat_fn=None, ruido: set | None = None):
    """-> (plan, banderas). `cat_fn()` entrega el catalogo de productos solo si hace falta (cargar las lineas cuesta)."""
    X, K = Texto(q), conocidos(dim)
    plan, expl = plan_vacio(), set()
    ban = {"ignoradas": [], "correcciones": {}, "entendio": False, "hereda": False, "avisos": []}

    _pedido_o_sku(X, dim, plan)
    _numericos(X, plan)
    per = _periodo(X, hoy, ban["avisos"])
    plan.update(per)
    if not per and X.hay(r"\b(?:del|de) dia\b") and X.hay(L.P_RESUMEN):
        plan["periodo"] = "hoy"
    if X.hay(L.P_HORAS):                                                  # el tablero solo guarda la fecha de creacion, no la hora
        plan["periodo"] = plan["periodo"] or "hoy"
        ban["avisos"].append("El tablero guarda solo la fecha de cada pedido (sin hora): te muestro el día completo.")
        X.marcar_tokens({"hora", "horas", "ultima", "ultimas", "ultimo", "por"})
    _estados(X, plan)                         # primero: "alerta BWS" no es el canal BWS, "alerta post" no es la bodega
    _entidades(X, K, plan)
    _agrupacion(X, plan)
    _metrica(X, plan)
    if X.hay(L.P_PCT_TOTAL) and plan["estado"] and plan["metrica"] in (None, "pedidos"):
        plan["metrica"] = "pct_estado"                                    # "cancelados vs total" = que parte del total son
        plan["comparar"] = False
        X.buscar(L.P_PCT_TOTAL)
    meses_citados = [m for m in L.MESES if m in X.todos()]
    if plan["comparar"] and len(meses_citados) >= 2:                      # "agosto vs julio": el mas reciente contra el anterior
        ult = max(meses_citados, key=lambda n: L.NUM_MES[n] if L.NUM_MES[n] <= hoy.month else L.NUM_MES[n] - 12)
        mes = L.NUM_MES[ult]
        ini = pd.Timestamp(hoy.year if mes <= hoy.month else hoy.year - 1, mes, 1)
        plan.update(periodo="rango", desde=_dia(ini), hasta=_dia(ini + pd.offsets.MonthEnd(0)))
        X.marcar_tokens(set(meses_citados))
    if plan["metrica"] == "distintos":
        m = re.search(r"(clientes|productos|skus?|canales|bodegas|modelos|articulos|clasificaciones|categorias)", X.t)
        plan["agrupar"] = {"clientes": "cliente", "productos": "producto", "sku": "producto", "skus": "producto", "canales": "canal", "bodegas": "bodega",
                           "modelos": "producto", "articulos": "producto", "clasificaciones": "clasif2", "categorias": "clasif2"}.get(m.group(1) if m else "", "cliente")
    if (m := X.buscar(L.P_SIN_ACTIVIDAD)):
        plan["agrupar"] = {"cliente": "cliente", "canal": "canal", "bodega": "bodega", "sla": "sla"}[m.group(1).rstrip("s").replace("canale", "canal")]
        plan["_sin"] = True
    super_ = plan.pop("_super", False)
    if super_ and not plan["metrica"]:                                    # "el mejor dia" = ventas; "el cliente con mas cancelaciones" = pedidos
        plan["metrica"] = "pedidos" if (plan["estado"] or X.hay(r"\bpedidos?\b|cancel|atras")) else "monto"
    if plan["agrupar"] == "mes" and not per:
        plan["periodo"] = "todo"                                          # "ventas por mes": todos los meses con datos
    elif plan["agrupar"] == "semana" and not per:
        plan["periodo"] = "ultimos"
        plan["dias"] = 84
    if plan["comparar"] and (m := re.search(r"(?:\bcon|\bvs|\bversus|\bcontra|respecto (?:a|al|del|de la))\s+(?:el|la)\s+(mes|semana)\s+(?:pasad[oa]|anterior)", X.t)) and X.hay(L.P_COMPARAR):
        if plan["periodo"] in ("mes_anterior", "semana_anterior"):          # "comparar ventas con el mes pasado" = este mes contra el pasado
            plan["periodo"] = "mes" if m.group(1) == "mes" else "semana"
    quitar = {"pct_integracion": "integrado", "pct_pendiente": "pendiente"}.get(plan["metrica"])
    if quitar in plan["estado"]:
        plan["estado"].remove(quitar)         # en "% pendiente" la palabra es la medida, no un filtro

    for k in ("pedido", "sku"):
        if plan[k]:
            expl.add("pedido" if k == "pedido" else "producto")
    if per:
        expl.add("periodo")
    for k in ("sla", "cliente", "canal", "bodega", "estado", "agrupar", "metrica", "top", "orden", "monto_min", "monto_max", "edad_min"):
        if plan[k]:
            expl.add(k)
    grande = X.buscar(L.P_PEDIDO_GRANDE)
    if grande and not plan["agrupar"]:
        plan.update(metrica="monto", orden="asc" if X.hay(r"\b(?:barato|chico|pequeno|menor)") else "desc",
                    top=plan["top"] or (1 if not X.hay(r"\bpedidos\b|ordenes") else 10))
        expl.update({"metrica", "orden", "top"})
    if plan["comparar"]:
        expl.add("comparar")

    # lo que sobra puede ser el nombre de un producto
    libres = [t for t in X.libres() if t not in L.STOP and t not in L.MESES and t not in (ruido or ()) and len(t) >= 2 and not (t.isdigit() and len(t) < 2)]
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
    sin_pedidos = not X.hay(r"\b(pedidos?|ordenes)\b")
    stock_cue = (X.hay(L.P_STOCK) or X.hay(L.P_STOCK_POCO) or X.hay(L.P_STOCK_COB)) and sin_pedidos
    listar = (X.hay(L.P_LISTAR) or bool(grande)) and (X.hay(L.P_ENTIDAD_LISTA) or bool(grande)) and not X.hay(L.P_CONTAR) and not plan["agrupar"] \
        and (plan["metrica"] in (None, "pedidos") or bool(grande) or X.hay(r"\bproductos?\b|\bqty\b|\bcant\w*|\bdetalle\b|\blistado\b|\blista\b"))             # "dime el monto de pedidos pendientes" es una cifra, no una lista
    saludo_solo = X.hay(L.P_SALUDO) and not expl and len(X.tok) <= 4 and not (X.hay(L.P_STOCK) or X.hay(L.P_STOCK_COB) or X.hay(L.P_ALERTAS) or X.hay(L.P_RESUMEN))
    if X.hay(L.P_AYUDA) or saludo_solo:
        plan["accion"] = "ayuda"
    elif X.hay(L.P_INFO):
        plan["accion"] = "info"
    elif plan["pedido"]:
        plan["accion"] = "pedido"
        plan["foco"] = ("lineas" if X.hay(L.P_FOCO_LINEAS) else "productos" if X.hay(L.P_FOCO_PRODUCTOS) else "estado" if X.hay(L.P_FOCO_ESTADO) else None)
    elif plan.pop("_sin", False):
        plan["accion"] = "sin_ventas"
    elif X.hay(L.P_SIN_VENTAS) and X.hay(r"\bproductos?\b|\bmodelos?\b|\bskus?\b|\barticulos?\b|\bque\b"):
        plan["accion"] = "sin_ventas"
    elif stock_cue:
        plan["accion"] = "stock"
        plan["stock_modo"] = ("poco" if X.hay(L.P_STOCK_POCO) else "cobertura" if X.hay(L.P_STOCK_COB) else "todo" if X.hay(L.P_STOCK_TODO)
                              else "sin" if X.hay(L.P_STOCK_SIN) else None)
    elif X.hay(L.P_ALERTAS) and not {"estado", "agrupar", "producto"} & expl:
        plan["accion"] = "alertas"
    elif X.hay(L.P_RESUMEN) and not {"agrupar", "metrica", "producto"} & expl and not plan["estado"]:
        plan["accion"] = "resumen"
    elif listar or (X.hay(r"\bpedidos?\b|\bordenes\b") and not plan["metrica"] and not plan["agrupar"] and not X.hay(L.P_CONTAR)
                    and ({"estado", "cliente", "bodega", "canal", "sla", "producto"} & expl)):
        plan["accion"] = "listar"
    elif expl:
        plan["accion"] = "medir"
    if plan["accion"] == "stock":
        plan["stock_modo"] = plan["stock_modo"] or ("sin" if not (plan["producto"] or plan["sku"]) else None)
        pats = (L.P_STOCK_POCO, L.P_STOCK_COB, L.P_STOCK_TODO, L.P_STOCK_SIN, L.P_STOCK)
    elif plan["accion"] == "alertas":
        pats = (L.P_ALERTAS,)
    elif plan["accion"] == "resumen":
        pats = (L.P_RESUMEN,)
    else:
        pats = ()
    for pat in pats:                                                      # las palabras que activaron la accion no son "sobrantes"
        for m in re.finditer(pat, X.t):
            X.marcar(m.start(), m.end())
    if plan["accion"]:
        expl.add("accion")
    ban["entendio"] = bool(plan["accion"])

    # seguimiento ("y ayer?", "ver los pedidos", "por cliente"): hereda lo que no se menciona
    propio = {"metrica", "producto", "pedido", "cliente", "canal", "bodega", "sla", "estado"} & expl     # una pregunta con tema propio no hereda
    corto = len(X.tok) <= 8 and not propio and bool(expl) and plan["accion"] not in ("stock", "alertas", "resumen", "sin_ventas", "pedido")
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
            elif k in ("stock_modo", "foco") and v:
                base[k] = v
            elif v not in (None, [], False) and k in expl:
                base[k] = v
        plan = base
        ban["hereda"] = True
    return plan, ban
