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


def kilos_posiciones(placed) -> list[dict]:
    """Kilos colocados por (camión, pallet, pedido). El peso de cada pieza viene de la Base de Medidas
    (Peso total); pallet 0 = carga a piso."""
    agg: dict[tuple, float] = {}
    for p in placed or []:
        k = (int(p.container), int(getattr(p, "pallet", 0) or 0), str(getattr(p, "ped", "") or ""))
        agg[k] = agg.get(k, 0.0) + float(p.peso or 0)
    return [{"camion": c, "pallet": n, "pedido": ped, "kilos": round(v, 1)} for (c, n, ped), v in sorted(agg.items())]


def _kg(pos: list[dict], camion: int, pallet: int | None = None) -> float:
    return round(sum(k["kilos"] for k in pos if k["camion"] == camion and (pallet is None or k["pallet"] == pallet)), 1)


def carga_por_camion(doc: dict) -> list[dict]:
    """[{camion, tipo, unidades, bultos, kilos, pallets: [{pallet, tipo, sucursal, unidades, bultos, kilos, lineas}], piso: {...}, lineas}]
    Usa el detalle por pallet (filas04) cuando existe; si no, las filas por camión (a piso)."""
    pos = doc.get("kilos_pos") or []
    camiones = doc.get("camiones") or []
    filas03 = doc.get("filas") or []
    filas04 = doc.get("filas04") or []
    out = []
    for c in camiones:
        num = c.get("numero")
        f04 = [f for f in filas04 if f.get("vehiculo") == num]
        item = {"camion": num, "tipo": c.get("tipo", ""), "kilos": _kg(pos, num), "pallets": [], "piso": None, "lineas": []}
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
                                        "unidades": un, "bultos": bu, "kilos": _kg(pos, num, int(n)), "lineas": lin})
            piso = _lineas([f for f in f04 if not f.get("pallet")])
            if piso:
                un, bu = _total(piso)
                item["piso"] = {"unidades": un, "bultos": bu, "kilos": _kg(pos, num, 0), "lineas": piso}
            todo = _lineas(f04)
        else:
            todo = _lineas([f for f in filas03 if f.get("camion") == num])
        item["lineas"] = todo
        item["unidades"], item["bultos"] = _total(todo)
        out.append(item)
    return out


def anotar(doc: dict, placed=None) -> dict:
    """Deja `carga_por_camion` y los totales de bultos y kilos en el documento de un cubicaje.
    Con `placed` (la carga colocada por el motor) se calculan los kilos; sin él se conservan los ya guardados."""
    if placed is not None:
        doc["kilos_pos"] = kilos_posiciones(placed)
    doc["carga_por_camion"] = carga_por_camion(doc)
    doc["bultos"] = sum(x["bultos"] for x in doc["carga_por_camion"])
    doc["kilos"] = round(sum(x["kilos"] for x in doc["carga_por_camion"]), 1)
    return doc


def completar_kilos(doc: dict) -> dict:
    """Cubicajes guardados antes de que existieran los kilos: el peso total de cada camión sale de los datos del visor
    (que ya lo traían). El peso por pallet solo se conoce al volver a cubicar."""
    cams = doc.get("carga_por_camion") or []
    if not cams or doc.get("kilos_pos") or any(c.get("kilos") for c in cams) or not doc.get("visor_json"):
        return doc
    import json
    try:
        pesos = {int(c.get("idx", i + 1)): float(c.get("pesoTot") or 0)
                 for i, c in enumerate(json.loads(doc["visor_json"]).get("camiones") or [])}
    except (ValueError, TypeError, AttributeError):
        return doc
    for c in cams:
        c["kilos"] = round(pesos.get(c["camion"], 0.0), 1)
    doc["kilos"] = round(sum(c["kilos"] for c in cams), 1)
    return doc
