"""Qué lleva cada camión y cada pallet: unidades y bultos.

Un bulto es lo que se mueve como una pieza: una caja master (con varias unidades dentro) o un producto suelto.
En modos a piso (MDA) cada unidad es un bulto, salvo las líneas que ya vienen como caja master.
"""
from __future__ import annotations


def _lineas(filas: list[dict]) -> list[dict]:
    """Suma por SKU (y sucursal) las filas de un camión, pallet o zona de piso."""
    agg: dict[tuple, dict] = {}
    for f in filas:
        k = (f.get("sucursal", ""), str(f.get("sku", "")))
        a = agg.setdefault(k, {"sku": str(f.get("sku", "")), "descripcion": f.get("descripcion", ""),
                               "sucursal": f.get("sucursal", ""), "bultos": 0, "unidades": 0})
        un = int(round(float(f.get("unidades") or 0)))
        bu = f.get("bultos")
        a["unidades"] += un
        a["bultos"] += int(round(float(bu))) if bu not in (None, "") else un
    return list(agg.values())


def _total(lineas: list[dict]) -> tuple[int, int]:
    return sum(x["unidades"] for x in lineas), sum(x["bultos"] for x in lineas)


def carga_por_camion(doc: dict) -> list[dict]:
    """[{camion, tipo, unidades, bultos, pallets: [{pallet, tipo, sucursal, unidades, bultos, lineas}], piso: {...}, lineas}]
    Usa el detalle por pallet (filas04) cuando existe; si no, las filas por camión (a piso)."""
    camiones = doc.get("camiones") or []
    filas03 = doc.get("filas") or []
    filas04 = doc.get("filas04") or []
    out = []
    for c in camiones:
        num = c.get("numero")
        f04 = [f for f in filas04 if f.get("vehiculo") == num]
        item = {"camion": num, "tipo": c.get("tipo", ""), "pallets": [], "piso": None, "lineas": []}
        if f04:
            por_pallet: dict[int, list[dict]] = {}
            for f in f04:
                if (f.get("pallet") or 0) > 0:
                    por_pallet.setdefault(int(f["pallet"]), []).append(f)
            for n in sorted(por_pallet):
                filas = por_pallet[n]
                lin = _lineas(filas)
                un, bu = _total(lin)
                item["pallets"].append({"pallet": n, "tipo": filas[0].get("tipo", ""), "sucursal": filas[0].get("sucursal", ""),
                                        "unidades": un, "bultos": bu, "lineas": lin})
            piso = _lineas([f for f in f04 if not f.get("pallet")])
            if piso:
                un, bu = _total(piso)
                item["piso"] = {"unidades": un, "bultos": bu, "lineas": piso}
            todo = _lineas(f04)
        else:
            todo = _lineas([f for f in filas03 if f.get("camion") == num])
        item["lineas"] = todo
        item["unidades"], item["bultos"] = _total(todo)
        out.append(item)
    return out


def anotar(doc: dict) -> dict:
    """Deja `carga_por_camion` y los totales de bultos en el documento de un cubicaje."""
    doc["carga_por_camion"] = carga_por_camion(doc)
    doc["bultos"] = sum(x["bultos"] for x in doc["carga_por_camion"])
    return doc
