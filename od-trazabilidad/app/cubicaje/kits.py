"""Kits en el cubicaje: un SKU que reúne cajas SEPARADAS (horno + encimera + campana) que deben ir juntas.

Un kit no tiene una medida propia: se cubica con las medidas de cada componente. Reglas:
- En pallet, el kit es indivisible: sus componentes viajan en el MISMO pallet. Se averigua cuántos kits completos
  caben en un pallet probando con las cajas reales, y se arman pallets de ese tamaño (más uno con el resto).
- Un pallet lleva UN solo tipo de kit. Existe `mezclar=True` para juntar en un pallet los restos de kits distintos,
  pero está apagado por defecto: falta validarlo con los analistas (ver docs/PENDIENTES.md).
- A piso, los kits se cargan por camiones completos de kits y el resto de los kits va primero en el siguiente
  camión; si aun así un kit queda partido entre camiones, se avisa.
- Si un solo kit no cabe en un pallet, va a piso.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .core import Item, Placement, Restric, cascada, pack
from .datos import Dims, get_dims_for
from .mda import Posicion
from .sda import Bloque, Pallet, _cubicar_pallet, _items_de_pallet
from .vb import clng

MAX_KITS_POR_LOTE = 400          # tope de la búsqueda de cuántos kits caben juntos


@dataclass
class KitDef:
    sku: str
    desc: str
    componentes: list[tuple[str, int]]            # (SKU, unidades por kit)


@dataclass
class LineaKit:
    kit: KitDef
    qty: int
    pedido: str
    sucursal: str = ""
    fila: int = 0


def _n(sku) -> str:
    return re.sub(r"^0+(?=\d)", "", str(sku or "").strip())


def separar_kits(posiciones: list[Posicion], kits: dict[str, KitDef] | None,
                 pasa_filtro=None) -> tuple[list[Posicion], list[LineaKit]]:
    """Saca de las posiciones las líneas que son kits. Las demás siguen su camino normal."""
    if not kits:
        return posiciones, []
    resto, lineas = [], []
    for p in posiciones:
        k = kits.get(_n(p.sku))
        if k is None:
            resto.append(p)
            continue
        if pasa_filtro is not None and not pasa_filtro(str(p.sku).strip()):
            continue
        qty = clng(p.carga) if isinstance(p.carga, (int, float)) else 0
        if qty > 0:
            ped = str(p.pedido).strip() or f"_row{p.fila}"
            lineas.append(LineaKit(kit=k, qty=qty, pedido=ped, fila=p.fila))
    return resto, lineas


def separar_kits_predist(posiciones: list[Posicion], predist: list, kits: dict[str, KitDef] | None,
                         pasa_filtro=None):
    """Como separar_kits, para los modos por sucursal: los kits salen del reparto (sucursal, kit, unidades), topeados
    por lo que trae el pedido, y cada fila queda como una línea de kit con su sucursal."""
    resto, lineas_pos = separar_kits(posiciones, kits, pasa_filtro)
    if not lineas_pos:
        return posiciones, predist, []
    disponible: dict[str, int] = {}
    pedido_de: dict[str, str] = {}
    for ln in lineas_pos:
        disponible[ln.kit.sku] = disponible.get(ln.kit.sku, 0) + ln.qty
        pedido_de.setdefault(ln.kit.sku, ln.pedido)
    normales, lineas = [], []
    for i, f in enumerate(predist):
        k = kits.get(_n(f.sku))
        if k is None:
            normales.append(f)
            continue
        und = clng(f.unidades) if isinstance(f.unidades, (int, float)) else 0
        und = min(und, disponible.get(k.sku, 0))
        suc = str(f.sucursal).strip().upper()
        if und <= 0 or not suc:
            continue
        disponible[k.sku] -= und
        lineas.append(LineaKit(kit=k, qty=und, pedido=pedido_de[k.sku], sucursal=suc, fila=i + 2))
    return resto, normales, lineas


def expandir_a_componentes(posiciones: list[Posicion], predist: list | None,
                           kits: dict[str, KitDef] | None) -> tuple[list[Posicion], list | None, list[str]]:
    """Para los modos que no arman pallets de kit: cada kit pasa a ser sus componentes sueltos (en el reparto
    por sucursal, los componentes de un kit quedan en la misma sucursal). Devuelve también los kits expandidos."""
    if not kits:
        return posiciones, predist, []
    usados: list[str] = []
    nuevas: list[Posicion] = []
    carga_kit: dict[str, int] = {}
    for p in posiciones:
        k = kits.get(_n(p.sku))
        if k is None:
            nuevas.append(p)
            continue
        qty = clng(p.carga) if isinstance(p.carga, (int, float)) else 0
        carga_kit[k.sku] = carga_kit.get(k.sku, 0) + qty
        if k.sku not in usados:
            usados.append(k.sku)
        for c, q in k.componentes:
            nuevas.append(Posicion(sku=c, desc=f"{p.desc} · componente de {k.sku}", carga=qty * q,
                                   pedido=p.pedido, fila=p.fila, cm_override=p.cm_override))
    nueva_pre = predist
    if predist is not None:
        from .mda_predist import FilaPredist
        nueva_pre, restante = [], dict(carga_kit)
        for f in predist:
            k = kits.get(_n(f.sku))
            if k is None:
                nueva_pre.append(f)
                continue
            und = clng(f.unidades) if isinstance(f.unidades, (int, float)) else 0
            und = min(und, restante.get(k.sku, 0))              # no más kits que los del pedido
            restante[k.sku] = restante.get(k.sku, 0) - und
            if und <= 0:
                continue
            for c, q in k.componentes:
                nueva_pre.append(FilaPredist(sucursal=f.sucursal, sku=c, unidades=und * q,
                                             por_bulto=int(getattr(f, "por_bulto", 0) or 0)))
    return nuevas, nueva_pre, usados


def _dims_de(linea: LineaKit, cache: dict[str, Dims]):
    dims = [get_dims_for(cache, c) for c, _ in linea.kit.componentes]
    faltan = [c for (c, _), d in zip(linea.kit.componentes, dims) if d is None]
    return dims, faltan


def _buscar_kits_por_unidad(cabe, total: int) -> int:
    """Cuántos kits caben en un contenedor: duplica hasta que no quepan y afina por búsqueda binaria."""
    if total < 1 or not cabe(1):
        return 0
    tope = min(total, MAX_KITS_POR_LOTE)
    lo, hi = 1, None
    c = 2
    while c <= tope:
        if cabe(c):
            lo, c = c, c * 2
        else:
            hi = c
            break
    if hi is None:
        if lo < tope and cabe(tope):
            return tope
        hi = tope + 1 if lo == tope else tope
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cabe(mid):
            lo = mid
        else:
            hi = mid
    return lo


# ---------------------------------------------------------------------------
# Pallets (SDA)
# ---------------------------------------------------------------------------
def armar_pallets_kit(lineas: list[LineaKit], cache: dict[str, Dims], bloques: list[Bloque], pal_L: float,
                      pal_W: float, pal_H: float, restric: Restric, mezclar: bool = False):
    """Arma los pallets de kits. Agrega a `bloques` los bloques de los componentes (después de los demás, así los
    índices existentes no cambian). Devuelve (pallets, placements, piso, avisos, sin_medidas): placements es una lista
    paralela a pallets; piso son (índice de bloque, cantidad) de los kits que no caben en un pallet."""
    pallets: list[Pallet] = []
    placements: list[list[Placement]] = []
    piso: list[tuple[int, int]] = []
    avisos: list[str] = []
    sin_medidas: list[str] = []
    parciales: list[int] = []

    for ln in lineas:
        dims, faltan = _dims_de(ln, cache)
        if faltan:
            sin_medidas += [c for c in faltan if c not in sin_medidas]
            avisos.append(f"Kit {ln.kit.sku} sin cubicar: faltan las medidas de {', '.join(faltan)}.")
            continue
        idx = []
        for (c, q), d in zip(ln.kit.componentes, dims):
            bloques.append(Bloque(cod=c, desc=f"{d.desc or c} (kit {ln.kit.sku})", tipo="Indiv", cm_por_caja=1,
                                  n=q * ln.qty, L=d.L, w=d.w, h=d.h, apilable=d.apilable, rotable=False,
                                  peso=d.peso, pedido=ln.pedido, sucursal=ln.sucursal,
                                  volumen=d.L * d.w * d.h))
            idx.append((len(bloques) - 1, q))
        memo: dict[int, tuple[bool, list[Placement]]] = {}

        def probar(kk: int, _idx=idx, _memo=memo):
            if kk not in _memo:
                pal = Pallet(contenido=[(bi, q * kk) for bi, q in _idx])
                plc, puestas = _cubicar_pallet(_items_de_pallet(pal, bloques), pal_L, pal_W, pal_H, restric)
                _memo[kk] = (puestas >= sum(q * kk for _, q in _idx), plc)
            return _memo[kk]

        k = _buscar_kits_por_unidad(lambda kk: probar(kk)[0], ln.qty)
        if k < 1:
            piso += [(bi, q * ln.qty) for bi, q in idx]
            avisos.append(f"Kit {ln.kit.sku}: ni un kit completo cabe en un pallet, va a piso.")
            continue
        llenos, resto = divmod(ln.qty, k)
        for kk in [k] * llenos + ([resto] if resto else []):
            pallets.append(Pallet(contenido=[(bi, q * kk) for bi, q in idx], frac=1.0, sucursal=ln.sucursal,
                                  tipo="Kit"))
            placements.append(probar(kk)[1])
            if kk < k:
                parciales.append(len(pallets) - 1)

    if mezclar and len(parciales) > 1:
        pallets, placements = _mezclar_restos(pallets, placements, parciales, bloques, pal_L, pal_W, pal_H, restric)
    return pallets, placements, piso, avisos, sin_medidas


def _mezclar_restos(pallets, placements, parciales, bloques, pal_L, pal_W, pal_H, restric):
    """Opción apagada por defecto: junta en un pallet los restos de kits distintos si TODO cabe (mismo destino)."""
    fuera: set[int] = set()
    for a in parciales:
        if a in fuera:
            continue
        for b in parciales:
            if b <= a or b in fuera or pallets[a].sucursal != pallets[b].sucursal:
                continue
            contenido = pallets[a].contenido + pallets[b].contenido
            prueba = Pallet(contenido=contenido)
            plc, puestas = _cubicar_pallet(_items_de_pallet(prueba, bloques), pal_L, pal_W, pal_H, restric)
            if puestas >= sum(n for _, n in contenido):
                pallets[a] = Pallet(contenido=contenido, frac=1.0, sucursal=pallets[a].sucursal, tipo="Kit mixto")
                placements[a] = plc
                fuera.add(b)
    keep = [i for i in range(len(pallets)) if i not in fuera]
    return [pallets[i] for i in keep], [placements[i] for i in keep]


# ---------------------------------------------------------------------------
# Piso (MDA y SDA a piso)
# ---------------------------------------------------------------------------
def _items_kit(ln: LineaKit, dims, kk: int) -> list[Item]:
    return [Item(cod=c, desc=f"{d.desc or c} (kit {ln.kit.sku})", L=d.L, w=d.w, h=d.h, peso=d.peso,
                 apilable=d.apilable, inclinable=False, rotable=False, qty=q * kk, fila=ln.fila, ped=ln.pedido)
            for (c, q), d in zip(ln.kit.componentes, dims)]


def preparar_piso(lineas: list[LineaKit], cache: dict[str, Dims], boxes: list, restric: Restric,
                  placed: list[Placement]):
    """Carga a piso los camiones COMPLETOS de kits (lo que cabe en el camión más grande) y devuelve:
    (camiones usados, caja de cada uno, items de los kits que quedan, avisos, SKU sin medidas).
    Los kits que sobran se entregan como items para que el cubicaje normal los cargue primero."""
    n_cont, cont_box = 0, [0]
    sobran: list[Item] = []
    avisos: list[str] = []
    sin_medidas: list[str] = []
    i_gr = len(boxes) - 1
    for ln in lineas:
        dims, faltan = _dims_de(ln, cache)
        if faltan:
            sin_medidas += [c for c in faltan if c not in sin_medidas]
            avisos.append(f"Kit {ln.kit.sku} sin cubicar: faltan las medidas de {', '.join(faltan)}.")
            continue

        def cabe(kk, _ln=ln, _d=dims):
            its = _items_kit(_ln, _d, kk)
            pack(its, boxes[i_gr], restric, [])
            return sum(i.qty for i in its) == 0

        k = _buscar_kits_por_unidad(cabe, ln.qty)
        restante = ln.qty
        if k >= 1 and ln.qty > k:                          # hay camiones completos de kits
            while restante >= k and restante > k:
                its = _items_kit(ln, dims, k)
                antes = len(placed)
                pack(its, boxes[i_gr], restric, placed)
                n_cont += 1
                cont_box.append(i_gr)
                for p in placed[antes:]:
                    p.container = n_cont
                restante -= k
                if sum(i.qty for i in its) > 0:            # no debería pasar: lo no puesto vuelve al cubicaje normal
                    sobran += [i for i in its if i.qty > 0]
        if restante > 0:
            sobran += _items_kit(ln, dims, restante)
    return n_cont, cont_box, sobran, avisos, sin_medidas


def kits_partidos(placed: list[Placement], lineas: list[LineaKit]) -> list[str]:
    """Kits cuyos componentes quedaron repartidos en camiones distintos (cantidades no proporcionales)."""
    avisos = []
    for ln in lineas:
        por_camion: dict[int, dict[str, int]] = {}
        for p in placed:
            if p.desc.endswith(f"(kit {ln.kit.sku})") and p.ped == ln.pedido:
                d = por_camion.setdefault(p.container, {})
                d[p.cod] = d.get(p.cod, 0) + p.n
        for cam, cant in por_camion.items():
            kits = {cant.get(c, 0) // q for c, q in ln.kit.componentes}
            sobrantes = any(cant.get(c, 0) % q for c, q in ln.kit.componentes)
            if len(kits) > 1 or sobrantes:
                avisos.append(f"El kit {ln.kit.sku} quedó partido entre camiones (el camión {cam} no lleva "
                              "todos sus componentes).")
                break
    return avisos


def cascada_con_kits(items: list[Item], lineas: list[LineaKit], cache: dict[str, Dims], boxes: list,
                     restric: Restric, placed: list[Placement]):
    """`cascada` normal, precedida de los camiones completos de kits. Devuelve (n_cont, cont_box, avisos, sin_medidas)."""
    if not lineas:
        n, cb = cascada(items, boxes, restric, placed)
        return n, cb, [], []
    n0, cb0, sobran, avisos, sin_medidas = preparar_piso(lineas, cache, boxes, restric, placed)
    resto: list[Placement] = []
    n1, cb1 = cascada(sobran + items, boxes, restric, resto)     # lo que sobra de kits va primero
    for p in resto:
        p.container += n0
    placed.extend(resto)
    avisos += kits_partidos(placed, lineas)
    return n0 + n1, cb0 + cb1[1:], avisos, sin_medidas
