"""Ajustes a mano del cubicaje: lo que el analista cambia en el visor 3D (mover, girar o quitar cajas, pasarlas a otro camión)
se vuelve a convertir en las cargas de cada camión (filas, pallets, bultos y kilos), para que las entregas, los PDF y los Excel
salgan de lo que realmente se va a cargar y no de la sugerencia original.

La verdad es el JSON del visor (una caja por cada bulto). De él se rehacen, por camión: la lista de lo que lleva cada uno
(`filas`, la hoja 03), el detalle por pallet (`filas04`, solo SDA), la geometría de los pallets, los vehículos y los totales."""
from __future__ import annotations

import json
from collections import OrderedDict
from types import SimpleNamespace

from . import resumen as resumen_carga


def _sku_de(cod: str, skus: set[str]) -> str:
    """Las cajas master viajan como «C» + SKU; las filas de la carga llevan el SKU (o el código de la caja, según el modo)."""
    if cod in skus:
        return cod
    if cod[:1] == "C" and cod[1:] in skus:
        return cod[1:]
    return cod


def _clave_fila(f: dict) -> tuple:
    return (str(f.get("sku", "")), str(f.get("pedido", "")), str(f.get("sucursal", "")))


def resumir_cambios(ant: dict, nuevo: dict) -> dict:
    """Cuántas cajas hay ahora en cada camión y cuántas cambiaron de camión o se quitaron (para avisar al analista)."""
    def conteo(d):
        return {int(c.get("idx") or i + 1): len(c.get("cajas") or []) for i, c in enumerate(d.get("camiones") or [])}
    a, n = conteo(ant), conteo(nuevo)
    return {"antes": sum(a.values()), "ahora": sum(n.values()), "por_camion": n}


def aplicar(doc: dict, visor_ant: str, visor_nuevo: str) -> dict:
    """Devuelve `doc` con las cargas rehechas a partir del visor ajustado. No toca el texto del visor: se guarda tal cual llegó."""
    nuevo = json.loads(visor_nuevo)
    ant = json.loads(visor_ant) if visor_ant else {"camiones": []}
    if not (nuevo.get("camiones") or []):
        raise ValueError("No hay camiones que guardar.")
    if (doc.get("filas04") or doc.get("pallets_detalle")) and ant.get("camiones") and \
            not any(b.get("pal") for c in ant["camiones"] for b in c.get("cajas") or []) and any((f.get("pallet") or 0) > 0 for f in doc.get("filas04") or []):
        raise ValueError("Este cubicaje se calculó antes de poder ajustarlo a mano: vuelve a cubicar y podrás mover las cajas.")
    camiones_v = sorted(nuevo.get("camiones") or [], key=lambda c: int(c.get("idx") or 0))
    filas_ant = doc.get("filas") or []
    skus = {str(f.get("sku", "")) for f in filas_ant} | {str(f.get("sku", "")) for f in (doc.get("filas04") or [])}
    plantillas = {}
    for f in filas_ant:
        plantillas.setdefault(_clave_fila(f), f)
    plantillas_sku = {}
    for f in filas_ant:
        plantillas_sku.setdefault(str(f.get("sku", "")), f)
    pedido_unico = str(doc.get("pedido") or "") if not doc.get("conjunto") else ""

    # ---- vehículos
    doc["camiones"] = [{"numero": int(c["idx"]), "tipo": c.get("tipo", ""), "L": c["L"], "w": c["W"], "h": c["H"],
                        "vol_m3": round(c["L"] * c["W"] * c["H"] / 1_000_000.0, 6)} for c in camiones_v]

    # ---- filas 03 y 04, y la lista de piezas con su peso (para los kilos)
    filas03: list[dict] = []
    filas04: list[dict] = []
    pesos: list = []
    pallets_ant = {int(p.get("numero")): p for p in (doc.get("pallets_detalle") or []) if p.get("numero") is not None}
    pallets_det: list[dict] = []
    es_sda = bool(doc.get("filas04") or doc.get("pallets_detalle"))
    f04_ant = {}
    for f in doc.get("filas04") or []:
        f04_ant.setdefault((str(f.get("sku", "")), str(f.get("pedido", "")), str(f.get("sucursal", ""))), f)

    for c in camiones_v:
        num = int(c["idx"])
        items = {str(it["cod"]): it for it in c.get("items") or []}
        vol_cap = c["L"] * c["W"] * c["H"] / 1_000_000.0 or 1.0
        grupos: OrderedDict = OrderedDict()
        por_pallet: OrderedDict = OrderedDict()
        for b in c.get("cajas") or []:
            cod = str(b["cod"])
            it = items.get(cod, {})
            m = max(int(it.get("m") or 1), 1)
            ped = str(b.get("ped") or pedido_unico)
            suc = str(b.get("suc") or "")
            sku = _sku_de(cod, skus)
            vol = (b["dx"] * b["dy"] * b["dz"]) / 1_000_000.0
            peso = float(it.get("pesoU") or 0.0)
            g = grupos.setdefault((sku, ped, suc), {"u": 0, "v": 0.0, "cajas": 0, "desc": it.get("desc", "")})
            g["u"] += m
            g["v"] += vol
            g["cajas"] += 1
            pal = int(b.get("pal") or 0)
            pf = por_pallet.setdefault((pal, sku, ped, suc), {"u": 0, "cajas": 0, "desc": it.get("desc", "")})
            pf["u"] += m
            pf["cajas"] += 1
            pesos.append(SimpleNamespace(container=num, pallet=pal, ped=ped, peso=peso))
        peds = list(dict.fromkeys(k[1] for k in grupos))
        tipo_carga = "Mono-pedido" if len(peds) <= 1 else f"Multi-pedido (n={len(peds)})"
        total_v = sum(g["v"] for g in grupos.values())
        acum = 0.0
        for (sku, ped, suc), g in grupos.items():
            acum += g["v"]
            base = plantillas.get((sku, ped, suc)) or plantillas_sku.get(sku) or {}
            fila = {k: v for k, v in base.items()}
            fila.update({"camion": num, "tipo_camion": c.get("tipo", ""), "cap_m3": round(vol_cap, 2), "sku": sku,
                         "descripcion": base.get("descripcion") or g["desc"], "unidades": g["u"],
                         "ocup_linea": g["v"] / vol_cap, "ocup_acum": acum / vol_cap, "libre_m3": round(vol_cap - acum, 2),
                         "fila_origen": base.get("fila_origen", 0), "tipo_carga": tipo_carga, "pedido": ped,
                         "pedidos_camion": ", ".join(peds), "sucursal": suc, "ocup_camion": total_v / vol_cap})
            filas03.append(fila)
        if es_sda:
            for (pal, sku, ped, suc), pf in por_pallet.items():
                base = f04_ant.get((sku, ped, suc)) or {}
                tipo_pal = "Piso" if pal == 0 else next((str(p.get("tipo") or "") for p in c.get("pallets") or [] if int(p.get("idx") or 0) == pal), "") or base.get("tipo", "Mono")
                filas04.append({"vehiculo": num, "tipo_vehiculo": c.get("tipo", ""), "pallet": pal, "sku": sku,
                                "descripcion": base.get("descripcion") or pf["desc"], "cajas": pf["cajas"], "bultos": pf["cajas"],
                                "unidades": pf["u"], "tipo": tipo_pal, "pedido": ped, "sucursal": suc})
        for p in c.get("pallets") or []:
            n_pal = int(p.get("idx") or 0)
            previo = dict(pallets_ant.get(n_pal) or {})
            previo.update({"numero": n_pal, "vehiculo": num, "x": p.get("x", 0), "y": p.get("y", 0), "dl": p.get("dl", 0),
                           "dw": p.get("dw", 0), "tipo": p.get("tipo") or previo.get("tipo", "")})
            if p.get("suc"):
                previo["sucursal"] = p["suc"]
            pallets_det.append(previo)

    doc["filas"] = filas03
    if es_sda:
        doc["filas04"] = filas04
        doc["pallets_detalle"] = pallets_det
    doc["unidades"] = sum(f["unidades"] for f in (filas04 or filas03))
    resumen_carga.anotar(doc, pesos)
    doc["ajustado"] = {"cajas_ahora": sum(len(c.get("cajas") or []) for c in camiones_v),
                       "cajas_antes": sum(len(c.get("cajas") or []) for c in ant.get("camiones") or [])}
    avisos = [a for a in (doc.get("avisos") or []) if not str(a).startswith("Ajustado a mano")]
    doc["avisos"] = avisos + ["Ajustado a mano en el 3D: las cargas de cada camión salen de lo que se dejó en el visor. "
                              "Volver a cubicar descarta estos ajustes."]
    return doc
