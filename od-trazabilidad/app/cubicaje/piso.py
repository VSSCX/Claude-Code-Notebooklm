"""SDA a piso: H2 = PISO fuerza la carga a piso aunque el modo sea SDA (EmpacarPisoYEscribir del VBA).

Los bloques se arman igual que en SDA (con caja master si corresponde) pero no se arman pallets:
las cajas van directo al camión. En Stock se respeta el orden de los bloques; en Predistribuido
va por sucursal, con el volumen más grande primero dentro de cada una (como MDA Predistribuido).
"""
from __future__ import annotations

from .core import Box, Item, cascada
from .datos import Dims
from .mda import NO_ENCONTRADO, Camion, Fila03, Posicion, Resultado
from .mda_predist import FilaPredist, restricciones_mda_predist
from .sda import Bloque, construir_bloques, restricciones_piso
from .sda_predist import construir_bloques_predist
from .vb import vb_round


def _items(bloques: list[Bloque], por_sucursal: bool) -> tuple[list[Item], dict[str, int]]:
    mult: dict[str, int] = {}
    orden = list(range(len(bloques)))
    if por_sucursal:                               # sucursal tal como vino; volumen DESC dentro de cada una
        sucs = list(dict.fromkeys(b.sucursal for b in bloques))
        orden = []
        for s in sucs:
            idx = [i for i, b in enumerate(bloques) if b.sucursal == s]
            idx.sort(key=lambda i: -bloques[i].L * bloques[i].w * bloques[i].h)
            orden += idx
    items = []
    for i in orden:
        b = bloques[i]
        cod = ("C" + b.cod) if b.tipo == "Caja" else b.cod
        mult[cod] = max(b.cm_por_caja, 1)
        items.append(Item(cod=cod, desc=b.desc, L=b.L, w=b.w, h=b.h, peso=b.peso, apilable=b.apilable,
                          rotable=False, inclinable=False, qty=b.n, fila=i + 1, ped=b.pedido,
                          suc=getattr(b, "sucursal", "") if por_sucursal else ""))
    return items, mult


def cubicaje_sda_a_piso(posiciones: list[Posicion], cache: dict[str, Dims], boxes: list[Box],
                        usa_caja_master: bool, predist: list[FilaPredist] | None = None,
                        pasa_filtro=None, cam_offset: int = 0) -> Resultado:
    por_suc = predist is not None
    res = Resultado(modo="SDA PREDISTRIBUIDO" if por_suc else "SDA STOCK")
    if not boxes:
        res.avisos.append("No hay camiones configurados.")
        return res
    if por_suc:
        bloques, sin_medidas, _ = construir_bloques_predist(predist, posiciones, cache, usa_caja_master, pasa_filtro)
    else:
        bloques, sin_medidas, sin_caja = construir_bloques(posiciones, cache, usa_caja_master, pasa_filtro)
        if sin_caja:
            res.avisos.append("Sin caja master, cubicados individuales: " + ", ".join(sin_caja))
    res.sin_medidas = sin_medidas
    res.no_encontrados = [p.sku for p in posiciones if str(p.desc).strip() == NO_ENCONTRADO]
    if not bloques:
        res.avisos.append("Sin SKUs cubicables.")
        return res
    res.avisos.append("Carga a piso (sin pallets): " + ("por sucursal." if por_suc else "las cajas van directo al camión."))

    items, mult = _items(bloques, por_suc)
    placed: list = []
    n_cont, cont_box = cascada(items, boxes, restricciones_mda_predist() if por_suc else restricciones_piso(), placed)
    res.placed = placed

    for c in range(1, n_cont + 1):
        bi = cont_box[c] if 1 <= c < len(cont_box) else len(boxes) - 1
        box = boxes[bi if 0 <= bi < len(boxes) else len(boxes) - 1]
        vol_cam = box.vol_m3 or 1.0
        del_cam = [p for p in placed if p.container == c]
        res.camiones.append(Camion(numero=c + cam_offset, tipo=box.tipo, L=box.L, w=box.w, h=box.h))
        agg: list[dict] = []
        for p in del_cam:
            f = next((a for a in agg if a["cod"] == p.cod and a["suc"] == p.suc and a["ped"] == p.ped), None)
            if f is None:
                f = {"suc": p.suc, "cod": p.cod, "desc": p.desc, "u": 0, "v": 0.0, "fila": p.fila, "ped": p.ped}
                agg.append(f)
            f["u"] += p.n * mult.get(p.cod, 1)
            f["v"] += p.volM3
        peds = list(dict.fromkeys(a["ped"] for a in agg))
        acum = 0.0
        for a in agg:
            acum += a["v"]
            res.filas03.append(Fila03(
                camion=c + cam_offset, tipo_camion=box.tipo, cap_m3=vb_round(box.vol_m3, 2), sku=a["cod"],
                descripcion=a["desc"], unidades=a["u"], ocup_linea=a["v"] / vol_cam, ocup_acum=acum / vol_cam,
                libre_m3=vb_round(box.vol_m3 - acum, 2), fila_origen=a["fila"],
                tipo_carga=f"Sucursal {a['suc']}" if por_suc else ("Mono-pedido" if len(peds) <= 1 else f"Multi-pedido (n={len(peds)})"),
                pedido=a["ped"], pedidos_camion=", ".join(peds), sucursal=a["suc"]))

    restante = {it.cod: it.qty * mult.get(it.cod, 1) for it in items if it.qty > 0}
    if restante:
        res.sin_ubicar = restante
        res.avisos.append("Unidades que no se pudieron ubicar: " + ", ".join(f"{k}: {v}" for k, v in restante.items()))
    return res
