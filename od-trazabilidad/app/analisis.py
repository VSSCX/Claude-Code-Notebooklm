"""Análisis del pedido: port exacto de las fórmulas de la hoja 02_Posiciones.

Columnas del Excel -> campos aquí:
  J Qty Entrega (VL01N)      -> qty_entrega      K Qty Pendiente -> pendiente
  M PLAN SOP M0              -> plan             N REAL          -> real
  O Qty En Entrega (ZSD)     -> en_entrega       T Saldo SOP     -> saldo = M - N - O
  F CARGA = max(0, min(J, T))                    G % OCUP = carga / Máx Camión
  H Ocupa acumulado          U Alerta            V Disponibilidad    W Orden
"""
import re
import unicodedata

SIN_STOCK, PARCIAL, LIMITADO, COMPLETO = "Sin stock", "Stock parcial", "Limitado SOP", "Completo"
ORDEN = {SIN_STOCK: 1, PARCIAL: 2, LIMITADO: 3, COMPLETO: 4}
ALERTADAS = (SIN_STOCK, PARCIAL, LIMITADO)

# Tabla "Clientes" del Excel: cliente -> (grupoSOP, código solicitante)
CLIENTES = {
    "EASY": ("Easy Retail S.A.", "272186"), "WALMART": ("Walmart Chile S.A.", "234482"),
    "RIPLEY": ("Comercial Eccsa S.A.", "232280"), "SODIMAC": ("SODIMAC S.A.", "200070"),
    "PARIS": ("Paris", "266566"), "FALABELLA": ("Falabella Retail S.A.", "237141"),
    "LA POLAR": ("Empresas La Polar S.A.", "232511"), "HITES": ("Hites S.A.", "231897"),
    "MULTICENTRO": ("Comercial Multicentro Limitada", "235225"),
    "DIMARSA": ("Distribuidora importadora Dimarsa", "234411"),
    "TOTTUS": ("Hipermercados Tottus S.A.", "234920"), "ABC": ("ABCDIN", "232276"),
    "CARRASCO": ("REGION 3", "237384"), "COMERCIAL FBT": ("REGION 2", "261764"),
    "COMERCIAL FDO. DÍAZ": ("REGION 2", "271686"), "COMERCIAL GERMANI": ("REGION 2", "231882"),
    "COMERCIAL MULTIHOME": ("REGION 2", "265872"), "COMERCIAL NK LIMITADA": ("REGION 2", "270101"),
    "COMERCIAL SOCOEPA S.A.": ("REGION 3", "231861"), "COOPELAN": ("REGION 2", "231934"),
    "COOPERCARAB": ("REGION 2", "232652"), "COPELEC": ("REGION 3", "233256"),
    "EMILIO HANANIA E HIJOS S.A.": ("REGION 2", "235242"),
    "ESTABLECIMIENTOS GERMANI": ("REGION 2", "231904"),
    "FERRETERIAS WEITZLER S.A.": ("REGION 2", "234410"),
    "GABRIEL MOCARQUER E HIJOS LTDA.": ("REGION 2", "231942"), "GONART": ("REGION 2", "231866"),
    "INVERISONES JULIAN": ("REGION 2", "243970"), "JAVER": ("REGION 2", "231923"),
    "MULTIHOGAR": ("REGION 3", "233443"), "SIEGMUND HNOS. LTDA.": ("REGION 2", "231875"),
    "ZÚÑIGA": ("REGION 3", "231959"),
}


# Pallet por cliente (hoja "Clientes", columnas D/E/F). Default del VBA: 120 x 100 x 140.
PALLETS = {
    "EASY": (120, 100, 150), "WALMART": (120, 100, 150), "RIPLEY": (120, 100, 160),
    "SODIMAC": (120, 100, 120), "PARIS": (120, 100, 150), "FALABELLA": (120, 100, 180),
    "LA POLAR": (120, 100, 150), "HITES": (120, 100, 140), "MULTICENTRO": (120, 100, 150),
    "DIMARSA": (120, 100, 150), "TOTTUS": (120, 100, 170), "ABC": (120, 100, 150),
}


def pallet_cliente(cliente: str) -> tuple[float, float, float]:
    return PALLETS.get((cliente or "").strip().upper(), (120.0, 100.0, 140.0))


def grupo_sop(cliente: str) -> str:
    """Misma regla que la columna L (Llave) del Excel."""
    c = (cliente or "").strip().upper()
    if c == "LA POLAR":
        return "ABC"
    grupo = CLIENTES.get(c, ("", ""))[0]
    if grupo in ("REGION 2", "REGION 3"):
        return grupo
    return c


def codigo_cliente(cliente: str) -> str:
    return CLIENTES.get((cliente or "").strip().upper(), ("", ""))[1]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s or "")).strip().upper()
    return " ".join(s.split())


def modelo(descripcion_base: str) -> str:
    """'900276671 COCINA FM5SSC' -> 'COCINA FM5SSC' (lo que hace MID(...FIND(" ")...))."""
    d = str(descripcion_base or "").strip()
    return d.split(" ", 1)[1] if " " in d else ""


def _clave(s) -> str:
    """Nombre comparable: sin tildes, en mayúsculas y con cualquier signo como espacio
    ("LAVADORA MADEMSA 9,5 BZG" y "LAVADORA MADEMSA 9 5 BZG" pasan a ser el mismo)."""
    n = unicodedata.normalize("NFD", str(s or ""))
    n = "".join(c for c in n if not unicodedata.combining(c)).upper()
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", n).split())


def cruzar_en_entrega(modelos: dict[str, str], en_entrega: dict[str, float]) -> tuple[dict, dict, list]:
    """Une cada SKU del pedido con lo que trajo ZSD001_03, por nombre de material.

    El código SAP del pedido no calza con el del reporte, así que (igual que el SUMIF del Excel) se
    cruza por el nombre. Para no depender de que el nombre sea idéntico:
      1. mismo nombre (ignorando tildes, mayúsculas y signos);
      2. si no hay, el nombre del reporte que termina con el modelo (o al revés), solo si es uno
         solo y no lo reclamó otro SKU con nombre exacto ("MDWMT16W" ↔ "LAVADORA MADEMSA MDWMT16W").
    Devuelve (unidades por SKU, nombre del reporte usado por SKU, nombres del reporte sin SKU)."""
    ent: dict[str, float] = {}
    for k, v in en_entrega.items():
        ent[_clave(k)] = ent.get(_clave(k), 0.0) + float(v or 0)
    qty: dict[str, float] = {}
    usado: dict[str, str] = {}
    reclamados: set[str] = set()
    for sku, modelo_ in modelos.items():
        m = _clave(modelo_)
        if m and m in ent:
            qty[sku], usado[sku] = ent[m], m
            reclamados.add(m)
    for sku, modelo_ in modelos.items():
        m = _clave(modelo_)
        if not m or sku in usado:
            continue
        cand = [k for k in ent if k not in reclamados and min(len(k), len(m)) >= 4
                and (k.endswith(" " + m) or m.endswith(" " + k))]
        if len(cand) == 1:
            qty[sku], usado[sku] = ent[cand[0]], cand[0]
            reclamados.add(cand[0])
    return qty, usado, sorted(k for k in ent if k not in reclamados)


def en_entrega_por_modelo(filas_zsd: list[dict]) -> dict[str, float]:
    """SUMIF(Entregas!J:J, modelo, Entregas!M:M): Qty. En Entrega por nombre de material."""
    def col(fila, *nombres):
        claves = {_norm(k).replace(".", "").replace(" ", ""): k for k in fila}
        for n in nombres:
            k = claves.get(_norm(n).replace(".", "").replace(" ", ""))
            if k is not None:
                return fila[k]
        return None
    out: dict[str, float] = {}
    for f in filas_zsd:
        nombre = _clave(col(f, "Nombre Codigo de Material", "Nombre Código de Material") or "")
        try:
            q = float(str(col(f, "Qty. En Entrega", "Qty En Entrega") or 0).replace(",", "."))
        except ValueError:
            q = 0.0
        if nombre:
            out[nombre] = out.get(nombre, 0.0) + q
    return out


def alerta(j: float, k: float, t: float) -> str:
    if j == 0:
        return SIN_STOCK
    if j >= k and t >= k:
        return COMPLETO
    if t < k and t <= j:
        return LIMITADO
    return PARCIAL


def calcular(posiciones: list[dict], plan: dict, en_entrega: dict[str, float],
             medidas: dict, disponibilidad: dict, stock: dict | None = None,
             ajustes: dict | None = None) -> dict:
    """posiciones: [{sku, qty_entrega, qty_pendiente}] tal como las lee VL01N."""
    stock, ajustes = stock or {}, ajustes or {}
    en_ent_sku, cruce, sin_cruce = cruzar_en_entrega(
        {str(p["sku"]): modelo(medidas[str(p["sku"])]["desc"]) for p in posiciones if str(p["sku"]) in medidas},
        en_entrega)
    filas = []
    for p in posiciones:
        sku = str(p["sku"])
        med = medidas.get(sku)
        desc = med["desc"] if med else "Producto no Encontrado"
        j, k = float(p.get("qty_entrega") or 0), float(p.get("qty_pendiente") or 0)
        pl = plan.get(sku) or {}
        m, n = float(pl.get("plan") or 0), float(pl.get("vendido") or 0)
        o = en_ent_sku.get(sku, 0.0)
        t = m - n - o
        carga_calc = max(0.0, min(j, t))
        carga = float(ajustes[sku]) if sku in ajustes else carga_calc
        max_cam = med["max_camion"] if med else 0
        ocup = 0.0 if not med else (carga / max_cam if max_cam else None)
        al = alerta(j, k, t)
        d = disponibilidad.get(sku)
        filas.append({
            "sku": sku, "descripcion": desc, "qty_entrega": j, "pendiente": k, "cruce_zsd": cruce.get(sku, ""),
            "plan": m, "real": n, "en_entrega": o, "saldo": t,
            "carga_calculada": carga_calc, "carga": carga, "ajustada": sku in ajustes,
            "ocupacion": ocup, "alerta": al, "orden": ORDEN[al],
            "disponibilidad": "" if al == COMPLETO or not d else f"{d['cantidad']} - {d['fecha']}",
            "stock": stock.get(sku),
        })
    filas.sort(key=lambda f: f["orden"])             # OrdenarPorAlerta
    acumulado = 0.0
    for f in filas:
        acumulado += f["ocupacion"] or 0
        f["acumulado"] = acumulado
    return {"filas": filas, "ocupacion_total": acumulado, "zsd_sin_cruce": sin_cruce,
            "alertadas": [f["sku"] for f in filas if f["alerta"] in ALERTADAS]}
