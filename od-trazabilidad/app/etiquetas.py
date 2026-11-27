"""Etiquetas de los clientes: lectura de los archivos que mandan y cuadre contra lo despachado.

DIMARSA manda sus etiquetas por correo como ZPL (impresora Zebra), en un archivo .prn o .txt. Cada bloque
^XA … ^XZ es una FILA de la hoja (dos etiquetas lado a lado) y ^PQn repite esa fila n veces. En cada etiqueta:

    002 - 010 - 030            ubicación / familia del producto en el cliente
    MADEMSA                    marca
    [código de barras]         código del producto en DIMARSA (8 dígitos, ej. 01167226)
    L-2600000000028 (vertical) lote del envío
    LAVADORA MADEMSA 9,5KG BZG descripción (una o dos líneas)
    240086033                  código Electrolux, o el modelo cuando no hay (M300D, MDWMT18S)

Como las filas llevan dos etiquetas, en las costuras entre un producto y otro la fila mezcla dos productos:
por eso se cuenta etiqueta por etiqueta y no fila por fila.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field

CLIENTE_DIMARSA = "DIMARSA"
_SKU_NUMERICO = re.compile(r"^\d{6,}$")
_NOMBRE = re.compile(r"^(L-\d+)[_\- ](\d+)")        # L-2600000000028_584-etiquetas…: lote y cuántas etiquetas trae


class FormatoNoReconocido(ValueError):
    pass


@dataclass
class Etiqueta:
    ubicacion: str = ""
    marca: str = ""
    cod_cliente: str = ""
    lote: str = ""
    descripcion: str = ""
    sku_etiqueta: str = ""        # lo último que dice la etiqueta: código Electrolux o modelo


@dataclass
class Lectura:
    formato: str = "ZPL"
    etiquetas: list[tuple[Etiqueta, int]] = field(default_factory=list)       # (etiqueta, copias)
    bloques: int = 0
    filas: int = 0                # filas de la hoja que se imprimen (cada una lleva dos etiquetas)
    avisos: list[str] = field(default_factory=list)


def _norm_cod(c: str) -> str:
    """Sin ceros a la izquierda y en minúsculas: así se busca en la maestra de homologación."""
    return re.sub(r"^0+(?=\d)", "", str(c or "").strip()).lower()


def _campos(bloque: str, ancho: int) -> dict[int, list[dict]]:
    """Los campos de un bloque, agrupados por la columna (etiqueta) en que están."""
    columnas: dict[int, list[dict]] = {}
    mitad = max(ancho // 2, 1)
    for trozo in bloque.split("^FS"):
        fo = re.search(r"\^FO(\d+),(\d+)", trozo)
        fd = re.search(r"\^FD(.*)", trozo, re.S)
        if not fo or not fd:
            continue
        x, y = int(fo.group(1)), int(fo.group(2))
        columnas.setdefault(x // mitad, []).append({
            "x": x, "y": y, "texto": fd.group(1).strip(),
            "barras": "^BC" in trozo or "^B3" in trozo or "^BE" in trozo,
            "vertical": bool(re.search(r"\^A.B,", trozo)),                   # texto girado: el lote
        })
    return columnas


def _etiqueta(campos: list[dict]) -> Etiqueta | None:
    e = Etiqueta()
    textos = []
    for c in sorted(campos, key=lambda c: (c["y"], c["x"])):
        if c["barras"]:
            e.cod_cliente = c["texto"]
        elif c["vertical"]:
            e.lote = c["texto"]
        else:
            textos.append(c["texto"])
    if not e.cod_cliente or len(textos) < 3:
        return None
    e.ubicacion, e.marca, e.sku_etiqueta = textos[0], textos[1], textos[-1]
    e.descripcion = " ".join(textos[2:-1])
    return e


def leer_zpl(texto: str) -> Lectura:
    """Lee un archivo de etiquetas ZPL. Si no lo es, dice que no reconoce el formato."""
    bloques = re.findall(r"\^XA(.*?)\^XZ", texto or "", re.S)
    if not bloques:
        raise FormatoNoReconocido(
            "No reconozco este archivo: espero etiquetas en formato ZPL (las que empiezan con ^XA y terminan con ^XZ). "
            "Si es un TXT de otro formato, avísanos cómo viene para poder leerlo.")
    lec = Lectura(bloques=len(bloques))
    for b in bloques:
        pq = re.search(r"\^PQ(\d+)", b)
        copias = int(pq.group(1)) if pq else 1
        lec.filas += copias
        pw = re.search(r"\^PW(\d+)", b)
        columnas = _campos(b, int(pw.group(1)) if pw else 832)
        for _, campos in sorted(columnas.items()):
            e = _etiqueta(campos)
            if e is None:
                lec.avisos.append("Una etiqueta del archivo no tiene todos sus datos y no se cuenta.")
                continue
            lec.etiquetas.append((e, copias))
    return lec


def analizar(texto: str, nombre: str = "", homologacion: dict[str, str] | None = None) -> dict:
    """Resumen del archivo: etiquetas por producto, con el código Electrolux de cada uno y lo que no cuadra dentro del propio archivo."""
    lec = leer_zpl(texto)
    homologacion = homologacion or {}
    productos: OrderedDict[str, dict] = OrderedDict()
    lotes: set[str] = set()
    total = 0
    for e, n in lec.etiquetas:
        total += n
        if e.lote:
            lotes.add(e.lote)
        p = productos.get(e.cod_cliente)
        if p is None:
            p = productos[e.cod_cliente] = {
                "cod_cliente": e.cod_cliente, "descripcion": e.descripcion, "marca": e.marca,
                "ubicacion": e.ubicacion, "sku_etiqueta": e.sku_etiqueta, "etiquetas": 0}
        p["etiquetas"] += n
    avisos = list(dict.fromkeys(lec.avisos))
    for p in productos.values():
        h = homologacion.get(_norm_cod(p["cod_cliente"]), "")
        num = p["sku_etiqueta"] if _SKU_NUMERICO.match(p["sku_etiqueta"]) else ""
        p["sku"] = h or num
        p["origen_sku"] = "homologacion" if h else ("etiqueta" if num else "")
        if h and num and h != num:
            avisos.append(f"El código DIMARSA {p['cod_cliente']} se homologa a {h}, pero la etiqueta dice {num}. Se usa {h}.")
        if not p["sku"]:
            avisos.append(f"{p['descripcion']} (código DIMARSA {p['cod_cliente']}) trae «{p['sku_etiqueta']}» en vez de un código Electrolux "
                          "y no está en la maestra de homologación: no se puede cuadrar con la entrega.")
    m = _NOMBRE.match(nombre or "")
    esperadas = int(m.group(2)) if m else None
    if m and lotes and m.group(1) not in lotes:
        avisos.append(f"El nombre del archivo habla del lote {m.group(1)} y las etiquetas traen {', '.join(sorted(lotes))}.")
    if esperadas is not None and esperadas != total:
        avisos.append(f"El nombre del archivo dice {esperadas} etiquetas y adentro hay {total}.")
    if len(lotes) > 1:
        avisos.append(f"El archivo mezcla {len(lotes)} lotes: {', '.join(sorted(lotes))}.")
    return {
        "cliente": CLIENTE_DIMARSA, "formato": lec.formato, "archivo": nombre, "lote": ", ".join(sorted(lotes)),
        "total_etiquetas": total, "etiquetas_esperadas": esperadas, "bloques": lec.bloques,
        "filas_impresas": lec.filas,
        "productos": sorted(productos.values(), key=lambda p: (p["descripcion"], p["cod_cliente"])),
        "avisos": avisos,
    }


def cuadrar(etiquetas: list[dict], unidades: dict[str, int], descripciones: dict[str, str] | None = None) -> dict:
    """Compara, por producto, las etiquetas del archivo con las unidades de las entregas elegidas.

    `etiquetas`: [{sku, etiquetas, descripcion}] (los productos de `analizar`). `unidades`: código Electrolux → unidades."""
    descripciones = descripciones or {}
    por_sku: dict[str, dict] = OrderedDict()
    sin_codigo = 0
    for p in etiquetas:
        sku = str(p.get("sku") or "").strip()
        n = int(p.get("etiquetas") or 0)
        if not sku:
            sin_codigo += n
            continue
        f = por_sku.setdefault(sku, {"sku": sku, "descripcion": p.get("descripcion") or "", "etiquetas": 0})
        f["etiquetas"] += n
    for sku, u in unidades.items():
        f = por_sku.setdefault(sku, {"sku": sku, "descripcion": descripciones.get(sku, ""), "etiquetas": 0})
        f.setdefault("unidades", 0)
        f["unidades"] = f.get("unidades", 0) + int(u)
    filas = []
    for f in por_sku.values():
        f.setdefault("unidades", 0)
        f["diferencia"] = f["etiquetas"] - f["unidades"]
        f["estado"] = ("ok" if f["diferencia"] == 0 else "sin_entrega" if f["unidades"] == 0
                       else "sin_etiqueta" if f["etiquetas"] == 0 else "sobran" if f["diferencia"] > 0 else "faltan")
        filas.append(f)
    orden = {"sin_entrega": 0, "sin_etiqueta": 1, "faltan": 2, "sobran": 3, "ok": 4}
    filas.sort(key=lambda f: (orden[f["estado"]], f["descripcion"], f["sku"]))
    tot_e, tot_u = sum(f["etiquetas"] for f in filas), sum(f["unidades"] for f in filas)
    return {"filas": filas, "etiquetas": tot_e + sin_codigo, "unidades": tot_u, "sin_codigo": sin_codigo,
            "cuadra": sin_codigo == 0 and all(f["estado"] == "ok" for f in filas),
            "con_diferencia": sum(1 for f in filas if f["estado"] != "ok")}
