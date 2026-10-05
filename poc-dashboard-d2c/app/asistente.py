"""Asistente de consultas del dashboard: preguntas en lenguaje natural sobre los pedidos.

Como funciona (y por que es seguro):
  1. PLANIFICAR: la pregunta se traduce a un "plan" JSON con campos fijos (metrica, producto, periodo, canal, ...).
     - Por defecto con reglas en espanol (sin IA, sin internet, sin costo).
     - Opcional: un modelo de IA (Ollama local, servidor compatible con OpenAI o Claude) que SOLO devuelve ese JSON.
       Si la IA falla, responde algo invalido o no esta configurada, se usan las reglas.
  2. VALIDAR: el plan se limpia contra listas permitidas (metricas, periodos, canales y bodegas reales...).
  3. EJECUTAR: el servidor calcula la cifra con pandas sobre sus propios datos. La IA nunca ve los pedidos, nunca
     escribe SQL ni codigo, y no puede cambiar nada: solo se le envia el texto de la pregunta y los nombres de
     canales, clientes y bodegas.
"""
from __future__ import annotations

import difflib
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from collections import deque
from datetime import timedelta

import pandas as pd

from . import servicio
from .config import settings

METRICAS = ("unidades", "pedidos", "monto", "lineas")
PERIODOS = ("hoy", "ayer", "semana", "semana_anterior", "mes", "mes_anterior", "ultimos", "todo", "rango")
ESTADOS = ("no_integrado", "integrado", "cancelado", "pendiente", "facturado")
AGRUPAR = ("dia", "cliente", "canal", "bodega", "estado", "producto", "sla")
CAMPOS_LISTA = ("canal", "cliente", "bodega", "estado")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
         "octubre", "noviembre", "diciembre"]
NUM_MES = {n: i + 1 for i, n in enumerate(MESES[:9])} | {"setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
EJEMPLOS = ["¿Cuántas unidades del refrigerador MED 165B cayeron hoy?",
            "¿Cuántos pedidos de MELI ayer?",
            "Top 5 productos más vendidos este mes",
            "Monto de pedidos no integrados esta semana"]

STOP = set("""a al algo ante aqui ayer cada caer cayeron cayo caen cuantas cuantos cuanto cuanta cuales cual de del dia dias
dame dime el ella ellos en entraron entre es esa ese eso esta este estan fue fueron ha han hasta hay hoy la las le lo los
mes meses me mi mis muestrame muestra necesito no o para pasado pasada por porfa que quiero se semana ser si sin sobre son su sus
tengo tenemos todo todos todas un una unas unos y vendimos vendieron vendido vendidas vendidos vendio venta ventas vender
unidad unidades uds ud pieza piezas pedido pedidos orden ordenes pv pvs monto total totales linea lineas canal canales
cliente clientes bodega bodegas ingresaron ingreso ingresos llegaron llego anterior ultimo ultimos ultima ultimas
saber ver busca buscar top mas menos mejor mejores comparado con desde durante mismo misma modelo modelos producto productos
equipo equipos cayendo cuales quienes hubo tuvimos tuvo salieron salio generaron pendiente pendientes integrado integrados
integrada integradas cancelado cancelados cancelada canceladas facturado facturados facturada facturadas ranking agrupado
agrupados agrupa detalle valor plata dinero cuantos aproximadamente actual actuales ahora""".split())

_LOCK = threading.Lock()
_LLAMADAS: deque = deque(maxlen=60)


# --------------------------------------------------------------------------- utilidades de texto
def _sa(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _tokens(t: str) -> list[str]:
    t = re.sub(r"(?<=\d)[.,](?=\d)", "", _sa(t))      # 8,5 -> 85 (igual en la pregunta y en la descripcion del producto)
    return re.findall(r"[a-z0-9]+", t)


def _compacto(t: str) -> str:
    return "".join(_tokens(t))


def _uno(tok: str) -> list[str]:
    """Formas de una palabra para comparar: singular/plural simple."""
    v = [tok]
    if len(tok) > 3 and tok.endswith("es"):
        v.append(tok[:-2])
    if len(tok) > 3 and tok.endswith("s"):
        v.append(tok[:-1])
    return v


def info_motor() -> dict:
    m = settings.ia_modo
    if m not in ("ollama", "openai", "anthropic"):
        return {"modo": "reglas", "nombre": "Reglas (sin IA)", "modelo": None, "local": True}
    url = settings.ia_url or ("https://api.anthropic.com" if m == "anthropic" else "http://localhost:11434")
    local = bool(re.match(r"https?://(localhost|127\.|\[::1\])", url))
    modelo = settings.ia_modelo or ("claude-haiku-4-5-20251001" if m == "anthropic" else "")
    return {"modo": m, "nombre": ("IA local" if local else "IA externa") + (f" ({modelo})" if modelo else ""),
            "modelo": modelo, "local": local}


# --------------------------------------------------------------------------- conocimiento del negocio (valores reales)
def _conocidos(dim: pd.DataFrame) -> dict:
    u = lambda c: sorted(str(x) for x in dim[c].dropna().unique())  # noqa: E731
    return {"cliente": u("SalesChannelName"), "canal": u("Canal"), "bodega": u("warehouse"), "sla": u("SLA_Type")}


ALIAS_CLIENTE = {"mercadolibre": "MELI", "mercado libre": "MELI", "meli": "MELI", "ml": "MELI"}
ALIAS_BODEGA = {"post": "POST_Fechado", "pos": "POST_Fechado", "postfechado": "POST_Fechado", "post fechado": "POST_Fechado"}


# --------------------------------------------------------------------------- planificador por reglas
def _periodo(texto: str, tokens: list[str], hoy: pd.Timestamp):
    """-> (campos del plan, indices de tokens consumidos)."""
    p: dict = {}
    usados: set[int] = set()
    T = tokens
    has = lambda *w: any(x in T for x in w)  # noqa: E731

    def marca(*palabras):
        for i, t in enumerate(T):
            if t in palabras:
                usados.add(i)

    m = re.search(r"(?:ultimos|ultimas|ultimo|ultima|pasados|pasadas)\s+(\d{1,3})\s+dias?", texto)
    if m:
        p.update(periodo="ultimos", dias=max(1, min(int(m.group(1)), 400)))
        marca(m.group(1))
    elif re.search(r"semana\s+(pasada|anterior)", texto):
        p["periodo"] = "semana_anterior"
    elif re.search(r"mes\s+(pasado|anterior)", texto):
        p["periodo"] = "mes_anterior"
    elif has("anteayer"):
        p.update(periodo="rango", desde=(hoy - timedelta(days=2)).strftime("%Y-%m-%d"), hasta=(hoy - timedelta(days=2)).strftime("%Y-%m-%d"))
    elif has("hoy"):
        p["periodo"] = "hoy"
    elif has("ayer"):
        p["periodo"] = "ayer"
    elif re.search(r"(esta|la)\s+semana|semanal", texto):
        p["periodo"] = "semana"
    elif re.search(r"(este|el)\s+mes|mensual|mes\s+en\s+curso", texto):
        p["periodo"] = "mes"
    elif re.search(r"historic|desde siempre|en total|todo el periodo", texto):
        p["periodo"] = "todo"
    # fechas sueltas: dd/mm, dd-mm, dd/mm/aaaa o aaaa-mm-dd
    fechas = []
    for d, mm, a in re.findall(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b", texto):
        try:
            anio = int(a) if a else hoy.year
            anio += 2000 if anio < 100 else 0
            fechas.append(pd.Timestamp(anio, int(mm), int(d)))
        except ValueError:
            pass
    for a, mm, d in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", texto):
        try:
            fechas.append(pd.Timestamp(int(a), int(mm), int(d)))
        except ValueError:
            pass
    if fechas:
        fechas = sorted(set(fechas))
        p.update(periodo="rango", desde=fechas[0].strftime("%Y-%m-%d"), hasta=fechas[-1].strftime("%Y-%m-%d"))
    else:
        for nom in MESES:
            if nom in T and "periodo" not in p:
                m_ = NUM_MES[nom]
                anio = hoy.year if m_ <= hoy.month else hoy.year - 1
                ini = pd.Timestamp(anio, m_, 1)
                p.update(periodo="rango", desde=ini.strftime("%Y-%m-%d"), hasta=(ini + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"))
                marca(nom)
    # los numeros de las fechas no son parte del nombre de un producto
    for i, t in enumerate(T):
        if p.get("periodo") == "rango" and re.fullmatch(r"\d{1,4}", t):
            usados.add(i)
    return p, usados


def planificar_reglas(q: str, dim: pd.DataFrame, hoy: pd.Timestamp, previo: dict | None = None) -> tuple[dict, dict]:
    """-> (plan, banderas). Entiende lo que se pregunta mas comun; lo demas lo puede resolver la IA o se pide reformular."""
    texto = _sa(q)
    T = _tokens(q)
    K = _conocidos(dim)
    usados: set[int] = set()
    plan: dict = {"metrica": None, "producto": None, "sku": None, "pedido": None, "periodo": None, "dias": None,
                  "desde": None, "hasta": None, "canal": [], "cliente": [], "bodega": [], "estado": [],
                  "agrupar": None, "top": 10}
    expl: set[str] = set()

    # pedido o SKU por numero
    seqs = set(dim["Sequence"].astype(str))
    for i, t in enumerate(T):
        if t.isdigit() and len(t) >= 6 and t in seqs:
            plan["pedido"] = t
            usados.add(i)
        elif t.isdigit() and len(t) == 9:
            plan["sku"] = t
            usados.add(i)

    # periodo
    per, u = _periodo(texto, T, hoy)
    if per:
        plan.update(per)
        expl.add("periodo")
    usados |= u

    # clientes / canales / bodegas
    for cl in K["cliente"]:
        ct = _tokens(cl)
        if ct and all(t in T for t in ct):
            plan["cliente"].append(cl)
            usados |= {i for i, t in enumerate(T) if t in ct}
    for alias, cl in ALIAS_CLIENTE.items():
        at = alias.split()
        if cl in K["cliente"] and cl not in plan["cliente"] and (alias in texto if len(at) > 1 else alias in T) and alias != "ml":
            plan["cliente"].append(cl)
            usados |= {i for i, t in enumerate(T) if t in at}
    for ca in ("BWS", "MKP"):
        if ca.lower() in T and ca in K["canal"]:
            plan["canal"].append(ca)
            usados |= {i for i, t in enumerate(T) if t == ca.lower()}
    for b in K["bodega"]:
        if b.lower() in T:
            plan["bodega"].append(b)
            usados |= {i for i, t in enumerate(T) if t == b.lower()}
    for alias, b in ALIAS_BODEGA.items():
        if b in K["bodega"] and b not in plan["bodega"] and ((alias in texto) if " " in alias else (alias in T)):
            plan["bodega"].append(b)
            usados |= {i for i, t in enumerate(T) if t in alias.split() or t == "fechado"}
    if "fechado" in T:
        usados |= {i for i, t in enumerate(T) if t == "fechado"}
    for k in ("cliente", "canal", "bodega"):
        if plan[k]:
            expl.add(k)

    # estados
    if re.search(r"\bno\s+integrad|sin\s+pv\b|sin\s+ingres|no\s+ingres", texto):
        plan["estado"].append("no_integrado")
    elif re.search(r"\bintegrad", texto):
        plan["estado"].append("integrado")
    if re.search(r"cancelad", texto):
        plan["estado"].append("cancelado")
    if re.search(r"pendiente|por\s+preparar|sin\s+despach", texto):
        plan["estado"].append("pendiente")
    if re.search(r"facturad", texto):
        plan["estado"].append("facturado")
    if plan["estado"]:
        expl.add("estado")

    # agrupacion
    m = re.search(r"\b(?:por|segun|cada)\s+(dia|cliente|canal|bodega|estado|producto|sla|modelo)\b", texto)
    if m:
        plan["agrupar"] = {"modelo": "producto"}.get(m.group(1), m.group(1))
    elif re.search(r"mas vendid|ranking|\btop\b|mejores", texto):
        plan["agrupar"] = "producto" if re.search(r"producto|modelo|articulo|equipo|sku", texto) else (
            "cliente" if re.search(r"cliente", texto) else "producto")
    elif re.search(r"cada dia|dia a dia|diario", texto):
        plan["agrupar"] = "dia"
    n = re.search(r"\btop\s*(\d{1,2})\b|\b(\d{1,2})\s+(?:productos|modelos|clientes|mas)", texto)
    if n:
        plan["top"] = max(1, min(int(n.group(1) or n.group(2)), 30))
        for i, t in enumerate(T):
            if t == (n.group(1) or n.group(2)):
                usados.add(i)

    # metrica
    if re.search(r"\b(unidad|unidades|uds?|piezas)\b", texto):
        plan["metrica"] = "unidades"
    elif re.search(r"\b(monto|montos|ventas?|plata|dinero|valor|facturacion)\b|\$", texto):
        plan["metrica"] = "monto"
    elif re.search(r"\b(lineas?)\b", texto):
        plan["metrica"] = "lineas"
    elif re.search(r"\b(pedidos?|ordenes|orden|pvs?|cuantos)\b", texto):
        plan["metrica"] = "pedidos"
    if plan["metrica"]:
        expl.add("metrica")

    # producto = lo que sobra
    resto = [t for i, t in enumerate(T) if i not in usados and t not in STOP and t not in MESES and len(t) >= 2
             and not (t.isdigit() and len(t) < 2)]
    if resto and not plan["pedido"]:
        plan["producto"] = " ".join(resto)
        expl.add("producto")
    if plan["sku"]:
        expl.add("producto")
    if plan["pedido"]:
        expl.add("pedido")

    banderas = {"explicito": expl, "entendio": bool(expl)}
    # seguimiento ("y ayer?", "y de Falabella?"): hereda lo que no se menciona
    corto = not ({"metrica", "producto", "pedido"} & expl) and not plan["agrupar"] and len(T) <= 4 and bool(expl)
    if previo and (texto.strip().startswith("y ") or corto):
        base = _validar(previo, K, hoy)
        for k, v in plan.items():
            if k in ("canal", "cliente", "bodega", "estado"):
                if v:
                    base[k] = v
            elif k in ("periodo", "dias", "desde", "hasta"):
                if "periodo" in expl:
                    base[k] = v
            elif k in ("metrica", "producto", "pedido") and k in expl:
                base[k] = v
            elif k == "agrupar" and v:
                base[k] = v
        plan = base
        banderas["hereda"] = True
        banderas["entendio"] = True
    return plan, banderas


# --------------------------------------------------------------------------- validacion del plan (sirve para reglas e IA)
def _validar(p: dict, K: dict, hoy: pd.Timestamp) -> dict:
    p = p if isinstance(p, dict) else {}
    out: dict = {"metrica": p.get("metrica") if p.get("metrica") in METRICAS else None,
                 "producto": None, "sku": None, "pedido": None,
                 "periodo": p.get("periodo") if p.get("periodo") in PERIODOS else None,
                 "dias": None, "desde": None, "hasta": None,
                 "agrupar": p.get("agrupar") if p.get("agrupar") in AGRUPAR else None, "top": 10}
    for k in ("producto",):
        v = p.get(k)
        out[k] = re.sub(r"\s+", " ", str(v)).strip()[:80] if isinstance(v, (str, int)) and str(v).strip() else None
    for k in ("sku", "pedido"):
        v = p.get(k)
        out[k] = re.sub(r"\D", "", str(v))[:12] or None if v not in (None, "") else None
    try:
        out["dias"] = max(1, min(int(p.get("dias")), 400)) if p.get("dias") not in (None, "") else None
        out["top"] = max(1, min(int(p.get("top") or 10), 30))
    except (TypeError, ValueError):
        out["top"] = 10
    for k in ("desde", "hasta"):
        try:
            out[k] = pd.Timestamp(p.get(k)).strftime("%Y-%m-%d") if p.get(k) else None
        except (ValueError, TypeError):
            out[k] = None
    if out["periodo"] == "rango" and not (out["desde"] or out["hasta"]):
        out["periodo"] = None
    if out["periodo"] == "ultimos" and not out["dias"]:
        out["periodo"] = None
    for k in ("canal", "cliente", "bodega"):
        v = p.get(k) or []
        v = [v] if isinstance(v, str) else v
        validos = {_sa(x): x for x in K[k]}
        lista = []
        for x in v if isinstance(v, list) else []:
            y = validos.get(_sa(ALIAS_CLIENTE.get(_sa(x), x) if k == "cliente" else (ALIAS_BODEGA.get(_sa(x), x) if k == "bodega" else x)))
            if y and y not in lista:
                lista.append(y)
        out[k] = lista
    v = p.get("estado") or []
    v = [v] if isinstance(v, str) else v
    out["estado"] = [x for x in dict.fromkeys(v if isinstance(v, list) else []) if x in ESTADOS]
    return out


# --------------------------------------------------------------------------- planificador con IA (opcional)
def _llm(system: str, user: str) -> str:
    modo, t = settings.ia_modo, settings.ia_timeout
    modelo = settings.ia_modelo
    url = (settings.ia_url or "").rstrip("/")

    def post(u, cuerpo, cab):
        req = urllib.request.Request(u, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", **cab})
        with urllib.request.urlopen(req, timeout=t) as r:   # noqa: S310  (la URL la fija quien administra el .env)
            return json.loads(r.read().decode("utf-8"))

    if modo == "ollama":
        j = post((url or "http://localhost:11434") + "/api/chat",
                 {"model": modelo or "qwen2.5:7b", "stream": False, "format": "json", "options": {"temperature": 0},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, {})
        return j["message"]["content"]
    if modo == "openai":
        cab = {"Authorization": "Bearer " + settings.ia_clave} if settings.ia_clave else {}
        cuerpo = {"model": modelo or "local", "temperature": 0,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        try:
            j = post((url or "http://localhost:1234/v1") + "/chat/completions",
                     {**cuerpo, "response_format": {"type": "json_object"}}, cab)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 422):
                raise
            j = post((url or "http://localhost:1234/v1") + "/chat/completions", cuerpo, cab)   # servidores sin modo JSON
        return j["choices"][0]["message"]["content"]
    if modo == "anthropic":
        j = post((url or "https://api.anthropic.com") + "/v1/messages",
                 {"model": modelo or "claude-haiku-4-5-20251001", "max_tokens": 500, "temperature": 0, "system": system,
                  "messages": [{"role": "user", "content": user}]},
                 {"x-api-key": settings.ia_clave, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in j["content"])
    raise RuntimeError("IA no configurada")


def _prompt_sistema(K: dict, hoy: pd.Timestamp) -> str:
    return f"""Eres el traductor de preguntas de un dashboard de pedidos D2C (VTEX contra SAP). NO respondas la pregunta ni inventes cifras:
devuelve SOLO un objeto JSON con este esquema, sin texto adicional.
{{"metrica": "unidades|pedidos|monto|lineas", "producto": "texto del producto tal como lo dijo el usuario o null",
 "sku": "codigo de 9 digitos o null", "pedido": "numero de pedido (Sequence) o null",
 "periodo": "hoy|ayer|semana|semana_anterior|mes|mes_anterior|ultimos|todo|rango|null", "dias": "entero si periodo=ultimos",
 "desde": "AAAA-MM-DD si periodo=rango", "hasta": "AAAA-MM-DD si periodo=rango",
 "canal": [subconjunto de {json.dumps(K['canal'], ensure_ascii=False)}], "cliente": [subconjunto de {json.dumps(K['cliente'], ensure_ascii=False)}],
 "bodega": [subconjunto de {json.dumps(K['bodega'], ensure_ascii=False)}],
 "estado": [subconjunto de no_integrado, integrado, cancelado, pendiente, facturado],
 "agrupar": "dia|cliente|canal|bodega|estado|producto|sla|null", "top": entero}}
Reglas: hoy es {hoy.strftime('%Y-%m-%d')}. Si dice "unidades" la metrica es unidades; "cuantos pedidos" es pedidos; "monto/ventas" es monto.
Si hay producto y no dice la metrica, usa unidades. Si no dice el periodo, usa "mes". "Mercado Libre" es el cliente MELI.
Ejemplo: "cuantas unidades del refrigerador med 165b cayeron hoy" -> {{"metrica":"unidades","producto":"refrigerador med 165b","periodo":"hoy"}}"""


def planificar_ia(q: str, dim: pd.DataFrame, hoy: pd.Timestamp, previo: dict | None) -> dict | None:
    K = _conocidos(dim)
    usuario = q if not previo else f"(pregunta anterior en forma de plan: {json.dumps(previo, ensure_ascii=False)})\n{q}"
    txt = _llm(_prompt_sistema(K, hoy), usuario)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    return _validar(json.loads(m.group(0)), K, hoy)


# --------------------------------------------------------------------------- busqueda de productos
def _productos(lin: pd.DataFrame, texto: str | None, sku: str | None):
    """-> (SKUs que coinciden, descripciones, aproximado, sugerencias)."""
    cat = lin.drop_duplicates("SKU")[["SKU", "Descripcion"]]
    if sku:
        sel = cat[cat["SKU"] == sku]
        return list(sel["SKU"]), dict(zip(sel["SKU"], sel["Descripcion"])), False, []
    toks = [t for t in _tokens(texto or "") if t not in STOP]
    if not toks:
        return [], {}, False, []
    comp = {r.SKU: _compacto(r.Descripcion + " " + r.SKU) for r in cat.itertuples()}
    palabras = {r.SKU: set(_tokens(r.Descripcion)) for r in cat.itertuples()}

    def ok(sk, t):
        return any(v in palabras[sk] or v in comp[sk] for v in _uno(t))
    puntaje = {sk: sum(ok(sk, t) for t in toks) / len(toks) for sk in comp}
    dig = [t for t in toks if any(c.isdigit() for c in t)]
    mejor = max(puntaje.values(), default=0)
    exacto = [sk for sk, v in puntaje.items() if v == 1]
    desc = dict(zip(cat["SKU"], cat["Descripcion"]))
    if exacto:
        return exacto, {k: desc[k] for k in exacto}, False, []
    if mejor >= .6:
        cand = [sk for sk, v in puntaje.items() if v == mejor and all(any(x in comp[sk] for x in _uno(t)) for t in dig)]
        if cand:
            return cand, {k: desc[k] for k in cand}, True, []
    sug = difflib.get_close_matches(" ".join(toks), [d for d in desc.values() if d], n=4, cutoff=.3)
    return [], {}, False, sug


# --------------------------------------------------------------------------- ejecucion
def _rango(plan: dict, hoy: pd.Timestamp):
    p = plan["periodo"] or "mes"
    if p == "hoy":
        return hoy, hoy, f"Hoy ({hoy.strftime('%d-%m-%Y')})"
    if p == "ayer":
        d = hoy - timedelta(days=1)
        return d, d, f"Ayer ({d.strftime('%d-%m-%Y')})"
    if p == "semana":
        ini = hoy - timedelta(days=hoy.weekday())
        return ini, hoy, f"Esta semana ({ini.strftime('%d-%m')} al {hoy.strftime('%d-%m')})"
    if p == "semana_anterior":
        ini = hoy - timedelta(days=hoy.weekday() + 7)
        fin = ini + timedelta(days=6)
        return ini, fin, f"Semana pasada ({ini.strftime('%d-%m')} al {fin.strftime('%d-%m')})"
    if p == "mes_anterior":
        fin = hoy.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin, f"Mes pasado ({fin.strftime('%m-%Y')})"
    if p == "ultimos":
        n = plan["dias"] or 7
        return hoy - timedelta(days=n - 1), hoy, f"Últimos {n} días"
    if p == "todo":
        return None, None, "Todo el período con datos"
    if p == "rango":
        d, h = plan["desde"], plan["hasta"]
        d, h = (pd.Timestamp(d) if d else None), (pd.Timestamp(h) if h else None)
        if d is not None and h is not None and d > h:
            d, h = h, d
        etq = (f"{d.strftime('%d-%m-%Y')}" if d is not None and h is not None and d == h else
               f"Del {d.strftime('%d-%m-%Y') if d is not None else '…'} al {h.strftime('%d-%m-%Y') if h is not None else '…'}")
        return d, h, etq
    return hoy.replace(day=1), hoy, f"Mes en curso ({hoy.strftime('%m-%Y')})"


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def ejecutar(plan: dict, dim: pd.DataFrame, hoy: pd.Timestamp, lin_fn) -> dict:
    """Calcula el plan sobre los pedidos (dim) y, si hace falta, sobre las lineas (lin_fn() -> (lineas, info))."""
    notas: list[str] = []
    chips: list[str] = []
    ini, fin, etq = _rango(plan, hoy)
    chips.append(etq)
    fmin = dim["Creation_Date"].min()
    if ini is not None and ini < fmin:
        notas.append(f"Los datos parten el {fmin.strftime('%d-%m-%Y')}; lo anterior no está cargado.")

    d = dim
    if ini is not None:
        d = d[d["Creation_Date"] >= ini]
    if fin is not None:
        d = d[d["Creation_Date"] <= fin]
    for k, col in (("canal", "Canal"), ("cliente", "SalesChannelName"), ("bodega", "warehouse")):
        if plan[k]:
            d = d[d[col].isin(plan[k])]
            chips.append(_lista(plan[k]))
    nombres = {"no_integrado": "No integrados", "integrado": "Integrados", "cancelado": "Cancelados",
               "pendiente": "Pendientes", "facturado": "Facturados"}
    for e in plan["estado"]:
        d = d[{"no_integrado": d["Estado Ingreso"] == "No ingresado", "integrado": d["Estado Ingreso"] == "Ingresado",
               "cancelado": d["Estado Ingreso"] == "Cancelado VTEX", "pendiente": d["Status"] == "ready-for-handling",
               "facturado": d["Status"] == "invoiced"}[e]]
        chips.append(nombres[e])
    if "cancelado" not in plan["estado"]:
        nc = int((d["Estado Ingreso"] == "Cancelado VTEX").sum())
        d = d[d["Estado Ingreso"] != "Cancelado VTEX"]
        chips.append("Sin canceladas")
        if nc:
            notas.append(f"Se excluyeron {nc} pedidos cancelados.")

    metrica = plan["metrica"] or ("unidades" if (plan["producto"] or plan["sku"] or plan["agrupar"] == "producto") else "pedidos")
    con_lineas = bool(plan["producto"] or plan["sku"]) or metrica == "lineas" or plan["agrupar"] == "producto"
    productos: list[dict] = []
    base = d
    if con_lineas:
        lin, info = lin_fn()
        if (plan["producto"] and not info["mapa"]["descripcion"]) and not plan["sku"]:
            return {"ok": False, "texto": "No puedo buscar por nombre de producto: no encontré la columna de descripción en OrderItems. "
                    "Indica su nombre en el .env (ITEM_COL_DESC). Mientras tanto puedes preguntar por el código SAP "
                    "(9 dígitos). Columnas disponibles: " + ", ".join(info["columnas"]) + ".", "chips": chips, "notas": []}
        if plan["producto"] or plan["sku"]:
            skus, desc, aprox, sug = _productos(lin, plan["producto"], plan["sku"])
            if not skus:
                t = f"No encontré productos que coincidan con «{plan['producto'] or plan['sku']}»."
                if sug:
                    t += " ¿Quisiste decir: " + "; ".join(sug) + "?"
                return {"ok": False, "texto": t, "chips": chips, "notas": notas, "sin_producto": True}
            productos = [{"sku": k, "descripcion": desc[k]} for k in skus[:8]]
            if aprox:
                notas.append("Coincidencia aproximada: no todas las palabras calzan con un producto.")
            lin = lin[lin["SKU"].isin(skus)]
            chips.append(productos[0]["descripcion"] + (f" y {len(skus) - 1} más" if len(skus) > 1 else ""))
        m = lin.merge(d[["Sequence", "Creation_Date", "SalesChannelName", "Canal", "warehouse", "Estado Pedido", "SLA_Type"]],
                      on="Sequence", how="inner")
        base = m
        if metrica == "monto" and m["Monto"].isna().all():
            return {"ok": False, "texto": "No encontré la columna de precio en OrderItems, así que no puedo calcular montos por producto. "
                    "Indica su nombre en el .env (ITEM_COL_PRECIO). Columnas disponibles: " + ", ".join(info["columnas"]) + ".",
                    "chips": chips, "notas": notas}

    def valor(x: pd.DataFrame) -> float:
        if con_lineas:
            return {"unidades": x["Qty"].sum(), "pedidos": x["Sequence"].nunique(), "monto": x["Monto"].sum(), "lineas": len(x)}[metrica]
        return {"unidades": x["Unidades"].sum(), "pedidos": len(x), "monto": x["Total_Value"].sum(),
                "lineas": len(x)}[metrica]

    total = float(valor(base) or 0)
    npeds = int(base["Sequence"].nunique()) if len(base) else 0
    unidad = {"unidades": "unidades", "pedidos": "pedidos", "monto": "", "lineas": "líneas"}[metrica]
    res = {"ok": True, "metrica": metrica, "valor": total, "formato": "$" if metrica == "monto" else "n", "unidad": unidad,
           "pedidos": npeds, "chips": chips, "notas": notas, "productos": productos, "tabla": None, "etiqueta": etq}

    g = plan["agrupar"] or ("producto" if len(productos) > 1 else None)
    if g and len(base):
        col = {"dia": "Creation_Date", "cliente": "SalesChannelName", "canal": "Canal", "bodega": "warehouse",
               "estado": "Estado Pedido", "producto": "Descripcion", "sla": "SLA_Type"}[g]
        if col in base.columns:
            filas = [(k, float(valor(x) or 0), int(x["Sequence"].nunique())) for k, x in base.groupby(col, dropna=False)]
            filas.sort(key=(lambda r: r[0]) if g == "dia" else (lambda r: -r[1]))
            filas = filas[-plan["top"]:] if g == "dia" else filas[:plan["top"]]
            etiq = lambda k: k.strftime("%d-%m-%Y") if hasattr(k, "strftime") else str(k)  # noqa: E731
            res["tabla"] = {"cols": [{"dia": "Día", "cliente": "Cliente", "canal": "Canal", "bodega": "Bodega", "estado": "Estado",
                                      "producto": "Producto", "sla": "SLA Type"}[g], {"unidades": "Unidades", "pedidos": "Pedidos",
                                      "monto": "Monto", "lineas": "Líneas"}[metrica], "Pedidos"],
                            "filas": [[etiq(k), v] + ([n] if metrica != "pedidos" else []) for k, v, n in filas], "formato": res["formato"]}
            if g != "dia" and base[col].nunique() > plan["top"]:
                notas.append(f"Se muestran los primeros {plan['top']} de {base[col].nunique()}.")
            res["notas"] = notas
    return res


def _texto(res: dict, plan: dict, hoy: pd.Timestamp, dim: pd.DataFrame) -> str:
    v = res["valor"]
    num = f"${v:,.0f}".replace(",", ".") if res["formato"] == "$" else f"{v:,.0f}".replace(",", ".")
    m = res["metrica"]
    prod = ""
    if res["productos"]:
        n = len(res["productos"])
        prod = f" de {res['productos'][0]['descripcion']}" + (f" y {n - 1} variante{'s' if n > 2 else ''} parecida{'s' if n > 2 else ''}" if n > 1 else "")
    if v == 0:
        ult = dim["Creation_Date"].max()
        extra = f" El último pedido cargado es del {ult.strftime('%d-%m-%Y')}." if res["etiqueta"].startswith(("Hoy", "Ayer")) else ""
        return f"{res['etiqueta']}: no hay {'unidades' if m == 'unidades' else 'registros'}{prod} con esos criterios.{extra}"
    sujeto = {"unidades": f"{num} unidades", "lineas": f"{num} líneas", "monto": f"{num}" + ("" if prod else " en pedidos"),
              "pedidos": f"{num} pedido" + ("" if v == 1 else "s")}[m]
    np_ = f"{res['pedidos']:,}".replace(",", ".")
    en = f", en {np_} pedido{'s' if res['pedidos'] != 1 else ''}" if m != "pedidos" else ""
    return f"{res['etiqueta']}: {sujeto}{prod}{en}."


# --------------------------------------------------------------------------- punto de entrada
def _limite() -> bool:
    ahora = time.time()
    with _LOCK:
        while _LLAMADAS and ahora - _LLAMADAS[0] > 60:
            _LLAMADAS.popleft()
        if len(_LLAMADAS) >= 40:
            return False
        _LLAMADAS.append(ahora)
        return True


def responder(pregunta: str, previo: dict | None = None) -> dict:
    q = re.sub(r"\s+", " ", str(pregunta or "")).strip()[:300]
    motor = info_motor()
    if not q:
        return {"ok": False, "texto": "Escribe una pregunta.", "motor": motor["nombre"]}
    if not _limite():
        return {"ok": False, "texto": "Demasiadas consultas seguidas. Espera un minuto.", "motor": motor["nombre"], "limite": True}
    dim, hoy = servicio.base_pedidos()
    previo = _validar(previo, _conocidos(dim), hoy) if isinstance(previo, dict) else None   # lo que manda el navegador nunca llega crudo al plan ni a la IA
    plan, via, aviso, banderas = None, "reglas", None, {"explicito": set()}
    if motor["modo"] != "reglas":
        try:
            plan = planificar_ia(q, dim, hoy, previo)
            via = "ia" if plan is not None else "reglas"
            if plan is None:
                aviso = "La IA no devolvió un plan válido, usé las reglas."
        except Exception as e:  # noqa: BLE001
            aviso = "La IA no respondió, usé las reglas." + ("" if settings.serverless else f" ({str(e)[:90]})")
            plan = None
    if plan is None:
        plan, banderas = planificar_reglas(q, dim, hoy, previo)
        if not banderas["entendio"]:
            return {"ok": False, "texto": "No entendí la pregunta. Puedo contar unidades, pedidos, líneas o montos, por producto, "
                    "cliente, bodega, estado y período. Por ejemplo:", "ejemplos": EJEMPLOS, "motor": motor["nombre"], "aviso": aviso}
    plan = _validar(plan, _conocidos(dim), hoy)

    if plan["pedido"]:
        det = servicio.detalle_pedido(plan["pedido"])
        if not det:
            return {"ok": False, "texto": f"No encontré el pedido {plan['pedido']} en los datos cargados.", "motor": motor["nombre"], "plan": plan}
        p = det["pedido"]
        return {"ok": True, "tipo": "pedido", "motor": motor["nombre"], "via": via, "plan": plan, "aviso": aviso,
                "texto": f"Pedido {p['sequence']}: {p['estado']}, {p['cliente']}, creado el {p['fecha'][8:]}-{p['fecha'][5:7]}-{p['fecha'][:4]}, "
                         f"{int(p['unidades'])} unidad(es).", "pedido": p, "lineas": det["lineas"], "chips": [], "notas": []}

    def lin_fn():
        _, _, lin, info = servicio.lineas_todas()
        return lin, info
    try:
        res = ejecutar(plan, dim, hoy, lin_fn)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "texto": "No pude calcular la respuesta." + ("" if settings.serverless else f" Detalle: {str(e)[:160]}"),
                "motor": motor["nombre"], "plan": plan}
    if res.get("sin_producto") and via == "reglas" and banderas["explicito"] <= {"producto"}:
        return {"ok": False, "texto": "No entendí la pregunta. Puedo contar unidades, pedidos, líneas o montos, por producto, "
                "cliente, bodega, estado y período. Por ejemplo:", "ejemplos": EJEMPLOS, "motor": motor["nombre"], "aviso": aviso}
    res.update(motor=motor["nombre"], via=via, plan=plan, aviso=aviso)
    if res.get("ok"):
        res["texto"] = _texto(res, plan, hoy, dim)
    return res
