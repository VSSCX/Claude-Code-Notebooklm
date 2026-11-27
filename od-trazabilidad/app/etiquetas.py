"""Etiquetas de los clientes: leer lo que manda el cliente, dejarlo en una tabla editable y bajarlo a Excel.

DIMARSA manda las etiquetas por correo de dos maneras, y las dos dicen lo mismo:

* TXT (N00481284.txt): una línea por producto, de ancho fijo (cp1252):
      0-8   código DIMARSA          48-68   marca
      8-48  nombre del artículo     68-88   atributo(6) + N° de orden de compra(6) + serie(8)
      88-108 código del proveedor (el de Electrolux, o el modelo)
      108-…  cantidad(14) + local(4) + rubro(4) + línea(4) + familia(4)
* PRN (L-2600000000028_584-etiquetas….prn): ZPL para impresora Zebra. Cada bloque ^XA…^XZ es una FILA de dos
  etiquetas y ^PQn la repite n veces; como en las costuras la fila mezcla dos productos, se cuenta etiqueta por
  etiqueta. La ubicación «002 - 010 - 030» es rubro - línea - familia.

El Excel que se baja es el mismo que armaba la consulta de Power Query («Importaciones Txt»): 12 columnas con los
datos del artículo y 4 auxiliares, una fila por producto.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from io import BytesIO

CLIENTE_DIMARSA = "DIMARSA"
_SKU_NUMERICO = re.compile(r"^\d{6,}$")
_NOMBRE = re.compile(r"^(L-\d+)[_\- ](\d+)")        # L-2600000000028_584-etiquetas…: lote y cuántas etiquetas trae
COD_USUARIO = 1588
LOCAL = "1006"

# Campos de una fila, en el orden de la tabla. «cantidad» y «local» no salen como columna propia en el Excel (van dentro de Column5).
CAMPOS = ("cod_interno", "nombre", "marca", "atributo", "orden_compra", "serie", "cod_proveedor", "precio",
          "cod_usuario", "rubro", "linea", "familia", "local", "cantidad")
COLUMNAS_EXCEL = ("Código Atríbuto Interno", "Nombre Artículo", "Marca Artículo", "Atributo Artículo", "Número Orden de Compra",
                  "Serie Orden de Compra", "Código Artículo Proveedor", "Precio", "Código Usuario", "Rubro Artículo",
                  "Línea Artículo", "Familia Artículo", "Source.Name", "Column1", "Column3", "Column5")
ANCHOS_EXCEL = (22, 44, 22, 18, 24, 20, 26, 10, 16, 15, 15, 16, 22, 52, 24, 22)


class FormatoNoReconocido(ValueError):
    pass


def _norm_cod(c: str) -> str:
    """Sin ceros a la izquierda y en minúsculas: así se busca en la maestra de homologación."""
    return re.sub(r"^0+(?=\d)", "", str(c or "").strip()).lower()


def _cinco(v: str) -> str:
    """Rubro, línea o familia como los trae el Excel: «0» + 4 dígitos («00010»)."""
    d = re.sub(r"\D", "", str(v or ""))
    return ("0" + d.zfill(4)[-4:]) if d else ""


def fila_vacia() -> dict:
    return {"cod_interno": "", "nombre": "", "marca": "", "atributo": "000000", "orden_compra": "", "serie": "", "cod_proveedor": "",
            "precio": "", "cod_usuario": COD_USUARIO, "rubro": "", "linea": "", "familia": "", "local": LOCAL, "cantidad": 0}


@dataclass
class Lectura:
    formato: str
    filas: list[dict] = field(default_factory=list)
    lotes: set[str] = field(default_factory=set)
    filas_impresas: int | None = None        # solo el PRN: filas de dos etiquetas que se imprimen
    avisos: list[str] = field(default_factory=list)


# ---------------- TXT ----------------
def leer_txt(texto: str) -> Lectura:
    lec = Lectura("TXT")
    for n, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue
        linea = linea.rstrip("\r\n")
        c5 = linea[108:].strip()
        if len(linea) < 108 or not re.match(r"^\d{8}", linea) or not re.fullmatch(r"\d{17,}", c5):
            lec.avisos.append(f"La línea {n} no tiene el formato esperado y no se leyó: «{linea[:60].strip()}».")
            continue
        f = fila_vacia()
        f.update(cod_interno=linea[:8], nombre=linea[8:48].rstrip(), marca=linea[48:68].strip(),
                 atributo=linea[68:74], orden_compra=linea[74:80], serie=linea[80:88].strip(),
                 cod_proveedor=linea[88:108].strip(), cantidad=int(c5[:-16] or 0), local=c5[-16:-12],
                 rubro=_cinco(c5[-12:-8]), linea=_cinco(c5[-8:-4]), familia=_cinco(c5[-4:]))
        lec.filas.append(f)
    if not lec.filas:
        raise FormatoNoReconocido("No pude leer ninguna línea de este TXT. Espero una línea por producto, de ancho fijo, como el N00481284.txt de DIMARSA.")
    return lec


# ---------------- PRN (ZPL) ----------------
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


def _etiqueta(campos: list[dict]) -> dict | None:
    e = {"cod_interno": "", "lote": ""}
    textos = []
    for c in sorted(campos, key=lambda c: (c["y"], c["x"])):
        if c["barras"]:
            e["cod_interno"] = c["texto"]
        elif c["vertical"]:
            e["lote"] = c["texto"]
        else:
            textos.append(c["texto"])
    if not e["cod_interno"] or len(textos) < 3:
        return None
    e.update(ubicacion=textos[0], marca=textos[1], cod_proveedor=textos[-1], nombre=" ".join(textos[2:-1]))
    return e


def leer_zpl(texto: str) -> Lectura:
    bloques = re.findall(r"\^XA(.*?)\^XZ", texto or "", re.S)
    if not bloques:
        raise FormatoNoReconocido("No reconozco este archivo: no es un TXT de DIMARSA ni etiquetas ZPL (las que empiezan con ^XA y terminan con ^XZ).")
    lec = Lectura("PRN", filas_impresas=0)
    por_cod: OrderedDict[str, dict] = OrderedDict()
    for b in bloques:
        pq = re.search(r"\^PQ(\d+)", b)
        copias = int(pq.group(1)) if pq else 1
        lec.filas_impresas += copias
        pw = re.search(r"\^PW(\d+)", b)
        for _, campos in sorted(_campos(b, int(pw.group(1)) if pw else 832).items()):
            e = _etiqueta(campos)
            if e is None:
                lec.avisos.append("Una etiqueta del archivo no tiene todos sus datos y no se cuenta.")
                continue
            if e["lote"]:
                lec.lotes.add(e["lote"])
            f = por_cod.get(e["cod_interno"])
            if f is None:
                f = fila_vacia()
                partes = [p.strip() for p in e["ubicacion"].split("-")]
                f.update(cod_interno=e["cod_interno"], nombre=e["nombre"], marca=e["marca"], cod_proveedor=e["cod_proveedor"])
                if len(partes) == 3:
                    f.update(rubro=_cinco(partes[0]), linea=_cinco(partes[1]), familia=_cinco(partes[2]))
                por_cod[e["cod_interno"]] = f
            f["cantidad"] += copias
    lec.filas = list(por_cod.values())
    if lec.filas:
        lec.avisos.append("El PRN no trae el número de orden de compra ni la serie: si los necesitas en el Excel, escríbelos en la tabla.")
    return lec


def leer(texto: str, nombre: str = "", homologacion: dict[str, str] | None = None) -> dict:
    """Lee un archivo de DIMARSA (TXT de ancho fijo o ZPL) y lo deja como tabla, con los avisos de lo que no cuadra."""
    homologacion = homologacion or {}
    lec = leer_zpl(texto) if "^XA" in (texto or "") else leer_txt(texto or "")
    avisos = list(dict.fromkeys(lec.avisos))
    total = sum(f["cantidad"] for f in lec.filas)
    if lec.formato == "PRN":
        m = _NOMBRE.match(nombre or "")
        if m and lec.lotes and m.group(1) not in lec.lotes:
            avisos.append(f"El nombre del archivo habla del lote {m.group(1)} y las etiquetas traen {', '.join(sorted(lec.lotes))}.")
        if m and int(m.group(2)) != total:
            avisos.append(f"El nombre del archivo dice {m.group(2)} etiquetas y adentro hay {total}.")
        if len(lec.lotes) > 1:
            avisos.append(f"El archivo mezcla {len(lec.lotes)} lotes: {', '.join(sorted(lec.lotes))}.")
        esperadas = int(m.group(2)) if m else None
    else:
        esperadas = None
    ordenes = sorted({f["orden_compra"] for f in lec.filas if f["orden_compra"]})
    if len(ordenes) > 1:
        avisos.append(f"El archivo mezcla {len(ordenes)} órdenes de compra: {', '.join(ordenes)}.")
    for f in lec.filas:
        sku = sku_de(f, homologacion)
        if not sku:
            avisos.append(f"{f['nombre']} (código DIMARSA {f['cod_interno']}) trae «{f['cod_proveedor']}» en vez de un código Electrolux "
                          "y no está en la maestra de homologación: no se puede cuadrar con la entrega.")
        elif homologacion.get(_norm_cod(f["cod_interno"])) not in (None, sku) and _SKU_NUMERICO.match(f["cod_proveedor"]):
            avisos.append(f"El código DIMARSA {f['cod_interno']} se homologa a {homologacion[_norm_cod(f['cod_interno'])]}, "
                          f"pero el archivo dice {f['cod_proveedor']}.")
    return {"cliente": CLIENTE_DIMARSA, "formato": lec.formato, "archivo": nombre, "lote": ", ".join(sorted(lec.lotes)),
            "orden_compra": ", ".join(ordenes), "total_etiquetas": total, "etiquetas_esperadas": esperadas,
            "filas_impresas": lec.filas_impresas, "filas": lec.filas, "avisos": avisos}


def sku_de(fila: dict, homologacion: dict[str, str] | None = None) -> str:
    """Código Electrolux de una fila: el que trae el archivo si es un código, si no el de la maestra de homologación."""
    cod = str(fila.get("cod_proveedor") or "").strip()
    if _SKU_NUMERICO.match(cod):
        return cod
    return (homologacion or {}).get(_norm_cod(fila.get("cod_interno")), "")


# ---------------- Excel ----------------
def _entero(v, defecto=0) -> int:
    try:
        return max(int(float(str(v).strip().replace(",", "."))), 0)
    except ValueError:
        return defecto


def excel(filas: list[dict], archivo: str = "") -> bytes:
    """El mismo Excel que armaba la consulta de Power Query: columnas A–L con el artículo y M–P auxiliares (Column5 lleva la cantidad)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.worksheet.table import Table, TableStyleInfo

    wb = Workbook()
    ws = wb.active
    ws.title = "Importaciones Txt"
    ws.append(list(COLUMNAS_EXCEL))
    for f in filas:
        nombre, serie = str(f.get("nombre", "")), str(f.get("serie", ""))
        atributo = str(f.get("atributo") or "000000")
        orden = str(f.get("orden_compra", ""))
        c1 = f"{str(f.get('cod_interno', ''))[:8]:<8}{nombre:<40}"
        c3 = f"{atributo[:6]:<6}{orden:<6}{serie:<8}"
        cuatro = lambda v: re.sub(r"\D", "", str(v or "")).zfill(4)[-4:]            # noqa: E731
        c5 = str(int(f"{_entero(f.get('cantidad')):014d}{cuatro(f.get('local') or LOCAL)}{cuatro(f.get('rubro'))}{cuatro(f.get('linea'))}{cuatro(f.get('familia'))}"))
        precio = str(f.get("precio", "")).strip()
        usuario = f.get("cod_usuario", COD_USUARIO)
        ws.append([str(f.get("cod_interno", "")), f"{nombre:<40}", f"{str(f.get('marca', '')):<20}", atributo, orden, f"{serie:<8}",
                   f"{str(f.get('cod_proveedor', '')):<20}", precio or None, _entero(usuario, COD_USUARIO) if str(usuario).strip() else None,
                   _cinco(f.get("rubro")), _cinco(f.get("linea")), _cinco(f.get("familia")), archivo, c1, c3, c5])
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, w in enumerate(ANCHOS_EXCEL):
        ws.column_dimensions[chr(65 + i)].width = w
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            if isinstance(c.value, str):
                c.number_format = "@"
    if filas:
        t = Table(displayName="Importaciones_Txt", ref=f"A1:P{len(filas) + 1}")
        t.tableStyleInfo = TableStyleInfo(name="TableStyleMedium7", showRowStripes=True)
        ws.add_table(t)
    ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- Cuadre contra las entregas ----------------
def productos_para_cuadre(filas: list[dict], homologacion: dict[str, str] | None = None) -> list[dict]:
    return [{"sku": sku_de(f, homologacion), "etiquetas": _entero(f.get("cantidad")), "descripcion": str(f.get("nombre", "")).strip()} for f in filas]


def cuadrar(etiquetas: list[dict], unidades: dict[str, int], descripciones: dict[str, str] | None = None) -> dict:
    """Compara, por producto, las etiquetas con las unidades de las entregas elegidas.

    `etiquetas`: [{sku, etiquetas, descripcion}]. `unidades`: código Electrolux → unidades."""
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
