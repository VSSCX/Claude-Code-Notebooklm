"""Port de Cubicaje_MDA_Predistribuido: carga a piso, agrupada por sucursal.

Diferencias con MDA:
- Las cantidades salen de la tabla Predistribuido (sucursal, SKU, unidades), topeadas
  por la carga SOP de cada SKU (lo que sobra del tope se descarta, en orden de la tabla).
- Las filas se ordenan por sucursal con el mismo quicksort del VBA (QSortMDP), que no
  es estable: dentro de una sucursal el orden depende del pivote, y eso afecta la carga.
- Cada sucursal es un bloque: dentro se ordena por volumen descendente y el motor solo
  permite invadir el espacio de la sucursal anterior (bloquePorSuc).
"""
from __future__ import annotations

from dataclasses import dataclass

from .core import Box, Item, Restric, cascada
from .datos import Dims, get_dims_for
from .mda import NO_ENCONTRADO, Camion, Fila03, Posicion, Resultado
from .vb import clng, vb_round


@dataclass
class FilaPredist:
    """Una fila de la hoja Predistribuido (columna E: unidades por bulto del cliente)."""
    sucursal: str
    sku: str
    unidades: float
    por_bulto: int = 0


def restricciones_mda_predist() -> Restric:
    return Restric(usaPeso=True, usaApilable=True, permiteRotar=False, permiteInclinar=False,
                   usaTopes=False, topeUnidades=0,
                   ordenarPorVolumen=False,   # el orden lo define sucursal + volumen del bloque
                   cargarDesdeFondo=True, respetarOrden=True, completarBloque=False,
                   motorBestFit=True, bloquePorSuc=True)


def _qsort_mdp(su: list, sk: list, qt: list, lo: int, hi: int) -> None:
    """QSortMDP: quicksort de Hoare, igual que el VBA (no es estable, y eso importa)."""
    if lo >= hi:
        return
    pivot = su[(lo + hi) // 2]
    i, j = lo, hi
    while True:
        while su[i] < pivot:
            i += 1
        while su[j] > pivot:
            j -= 1
        if i <= j:
            su[i], su[j] = su[j], su[i]
            sk[i], sk[j] = sk[j], sk[i]
            qt[i], qt[j] = qt[j], qt[i]
            i, j = i + 1, j - 1
        if i > j:
            break
    if lo < j:
        _qsort_mdp(su, sk, qt, lo, j)
    if i < hi:
        _qsort_mdp(su, sk, qt, i, hi)


def topear_por_sop(predist: list[FilaPredist], sop: dict[str, int]) -> tuple[list, list, list]:
    """Recorta el predistribuido al tope de la carga SOP, respetando el orden de la tabla."""
    usado: dict[str, int] = {}
    sucs, skus, qtys = [], [], []
    for f in predist:
        suc, sku = str(f.sucursal).strip(), str(f.sku).strip()
        if not suc or not sku:
            continue
        qd = clng(f.unidades) if isinstance(f.unidades, (int, float)) else 0
        if qd <= 0:
            continue
        limite = sop.get(sku, qd)                  # sin SOP para ese SKU: no se topea
        disponible = limite - usado.get(sku, 0)
        if disponible <= 0:
            continue
        qd = min(qd, disponible)
        usado[sku] = usado.get(sku, 0) + qd
        sucs.append(suc)
        skus.append(sku)
        qtys.append(qd)
    return sucs, skus, qtys


def cubicaje_mda_predistribuido(posiciones: list[Posicion], predist: list[FilaPredist],
                                cache: dict[str, Dims], boxes: list[Box], pasa_filtro=None,
                                cam_offset: int = 0, kits: dict | None = None) -> Resultado:
    from .kits import expandir_a_componentes
    res = Resultado(modo="MDA PREDISTRIBUIDO")
    posiciones, predist, _usados = expandir_a_componentes(posiciones, predist, kits)
    if not boxes:
        res.avisos.append("No hay camiones configurados.")
        return res

    # Tope por SKU según la carga del análisis (columna F del Excel)
    sop: dict[str, int] = {}
    for p in posiciones:
        sku = str(p.sku).strip()
        if not sku:
            continue
        if str(p.desc).strip() == NO_ENCONTRADO:
            res.no_encontrados.append(sku)
            continue
        if isinstance(p.carga, (int, float)):
            sop[sku] = sop.get(sku, 0) + clng(p.carga)

    sucs, skus, qtys = topear_por_sop(predist, sop)
    if not sucs:
        res.avisos.append("Sin datos válidos en Predistribuido (todo limitado por el SOP).")
        return res
    _qsort_mdp(sucs, skus, qtys, 0, len(sucs) - 1)

    items: list[Item] = []
    fila = 0
    while fila < len(sucs):
        suc_actual = sucs[fila]
        desde = len(items)
        while fila < len(sucs) and sucs[fila] == suc_actual:
            cod = skus[fila]
            if pasa_filtro is not None and not pasa_filtro(cod):
                fila += 1
                continue
            d = get_dims_for(cache, cod)
            if d is None:
                if cod not in res.sin_medidas:
                    res.sin_medidas.append(cod)
            else:
                items.append(Item(cod=cod, desc=d.desc or cod, L=d.L, w=d.w, h=d.h, peso=d.peso,
                                  apilable=d.apilable, inclinable=d.inclinable, rotable=d.rotable,
                                  qty=qtys[fila], fila=fila + 1, ped="", suc=suc_actual))
            fila += 1
        bloque = items[desde:]                     # volumen DESC dentro de la sucursal
        n = len(bloque)
        for a in range(n - 1):
            for b in range(n - 1 - a):
                v1 = bloque[b].L * bloque[b].w * bloque[b].h
                v2 = bloque[b + 1].L * bloque[b + 1].w * bloque[b + 1].h
                if v1 < v2:
                    bloque[b], bloque[b + 1] = bloque[b + 1], bloque[b]
        items[desde:] = bloque

    if not items:
        res.avisos.append("Sin SKUs cubicables en MDA Predistribuido.")
        return res

    placed: list = []
    n_cont, cont_box = cascada(items, boxes, restricciones_mda_predist(), placed)
    res.placed = placed

    # Salida por camión y sucursal (hoja 03 del modo predistribuido)
    for c in range(1, n_cont + 1):
        bi = cont_box[c] if 1 <= c < len(cont_box) else len(boxes) - 1
        box = boxes[bi if 0 <= bi < len(boxes) else len(boxes) - 1]
        vol_cam = box.vol_m3 or 1.0
        del_cam = [p for p in placed if p.container == c]
        ocup = sum(p.volM3 for p in del_cam) / vol_cam
        res.camiones.append(Camion(numero=c + cam_offset, tipo=box.tipo, L=box.L, w=box.w, h=box.h))
        agg: list[dict] = []
        for p in del_cam:
            f = next((a for a in agg if a["cod"] == p.cod and a["suc"] == p.suc), None)
            if f is None:
                f = {"suc": p.suc, "cod": p.cod, "desc": p.desc, "u": 0, "v": 0.0, "fila": p.fila}
                agg.append(f)
            f["u"] += p.n
            f["v"] += p.volM3
        acum = 0.0
        for a in agg:
            acum += a["v"]
            res.filas03.append(Fila03(
                camion=c + cam_offset, tipo_camion=box.tipo, cap_m3=vb_round(box.vol_m3, 2),
                sku=a["cod"], descripcion=a["desc"], unidades=a["u"],
                ocup_linea=a["v"] / vol_cam, ocup_acum=acum / vol_cam,
                libre_m3=vb_round(box.vol_m3 - acum, 2), fila_origen=a["fila"],
                tipo_carga=f"Sucursal {a['suc']}", pedido="", pedidos_camion="",
                sucursal=a["suc"], ocup_camion=ocup))

    restante = {it.cod: it.qty for it in items if it.qty > 0}
    if restante:
        res.sin_ubicar = restante
        res.avisos.append("Unidades que no se pudieron ubicar: " +
                          ", ".join(f"{k}: {v}" for k, v in restante.items()))
    return res
