"""Port de M_Cub_Core.bas: motor geométrico de cubicaje (geometría pura, en cm).

Heightmap (skyline 3D) columna-primero. Para cada producto busca la mejor
posición sobre el relieve ya cargado, apila una columna del mismo SKU y registra
una colocación (TPlacement) por columna. Reglas físicas: apilado, soporte >= 70%
de la base, no-pesado-sobre-liviano, no-apilable-nada-encima.

Se conservan los nombres del VBA en los comentarios para poder auditar línea a línea.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .vb import ceil_neg_int, vb_int

EPS = 0.5          # Private Const EPS As Double = 0.5
CELL = 2.0         # cm por celda del heightmap (2 = como el Excel; 1 = más fino y más lento)


def usar_celda(cm: float) -> None:
    """Cambia el tamaño de celda del heightmap. 2 cm es lo que usa el Excel."""
    global CELL
    CELL = 2.0 if cm not in (1.0, 2.0) else float(cm)
MAX_CAND = 20000   # ReDim candIX(1 To 20000)
PISO_PESO = 1e30   # el piso aguanta todo


@dataclass
class Item:                      # Public Type TItem
    cod: str
    desc: str = ""
    L: float = 0.0
    w: float = 0.0
    h: float = 0.0
    peso: float = 0.0
    apilable: bool = True
    rotable: bool = False
    inclinable: bool = False
    qty: int = 0
    fila: int = 0
    ped: str = ""
    suc: str = ""


@dataclass
class Box:                       # Public Type TBox
    tipo: str
    L: float
    w: float
    h: float

    @property
    def vol_m3(self) -> float:
        return self.L * self.w * self.h / 1_000_000.0


@dataclass
class Restric:                   # Public Type TRestric
    usaPeso: bool = False
    usaApilable: bool = False
    permiteRotar: bool = False
    permiteInclinar: bool = False
    usaTopes: bool = False
    topeUnidades: int = 0
    ordenarPorVolumen: bool = False
    cargarDesdeFondo: bool = False
    respetarOrden: bool = False
    completarBloque: bool = False
    motorBestFit: bool = False
    bloquePorSuc: bool = False


@dataclass
class Placement:                 # Public Type TPlacement
    cod: str
    desc: str
    ped: str
    container: int
    fila: int
    x: float
    y: float
    z: float
    oL: float
    oW: float
    oH: float
    n: int
    nivel: int
    volM3: float
    peso: float
    suc: str = ""
    pallet: int = 0        # 0 = va a piso; >0 = número de pallet
    pallet: int = 0        # modos SDA: número de pallet al que pertenece


@dataclass
class _Estado:
    """Heightmap de UN camión + candidatos de esquina."""
    nx: int
    ny: int
    hm: np.ndarray = field(init=False)
    pesoTop: np.ndarray = field(init=False)
    sopTop: np.ndarray = field(init=False)
    cand: list = field(default_factory=lambda: [(0, 0)])
    # Franjas de gx donde un producto (según clave) no tiene ninguna posición válida.
    # Se mantienen hasta que una colocación toca sus filas (ver invalidar_franjas).
    vacias: dict = field(default_factory=dict)

    def __post_init__(self):
        self.hm = np.zeros((self.nx, self.ny), dtype=float)
        self.pesoTop = np.full((self.nx, self.ny), PISO_PESO, dtype=float)
        self.sopTop = np.ones((self.nx, self.ny), dtype=bool)

    def copia(self) -> "_Estado":
        otra = _Estado.__new__(_Estado)
        otra.nx, otra.ny = self.nx, self.ny
        otra.hm, otra.pesoTop, otra.sopTop = self.hm.copy(), self.pesoTop.copy(), self.sopTop.copy()
        otra.cand = list(self.cand)
        otra.vacias = {k: set(v) for k, v in self.vacias.items()}
        return otra

    def invalidar_franjas(self, x0: int, x1: int) -> None:
        """Una colocación cambió las filas [x0, x1): las franjas que las leen dejan de valer."""
        for clave, franjas in self.vacias.items():
            cx = clave[0]                     # una franja [a, b) lee las filas [a, b + cx - 1)
            franjas.difference_update([f for f in franjas if f[0] < x1 and f[1] + cx - 1 > x0])


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def meter_en_camion(cL: float, cW: float, ch: float, items: list[Item], i_from: int, i_to: int,
                    restric: Restric, placed: list[Placement], acum: dict) -> None:
    """CubCore_MeterEnCamion. Índices i_from..i_to son 0-based INCLUSIVOS.
    acum = {"unid": int, "vol": float} (unidCam, volCam ByRef)."""
    if i_from < 0 or i_to < i_from:
        return
    if cL < CELL or cW < CELL or ch <= 0:
        return
    nx, ny = vb_int(cL / CELL), vb_int(cW / CELL)
    if nx < 1 or ny < 1:
        return
    est = _Estado(nx, ny)

    ordn = list(range(i_from, i_to + 1))
    m = len(ordn)
    if not restric.respetarOrden:
        # Burbuja idéntica a la del VBA (estable; mismas tolerancias)
        for a in range(1, m):
            for b in range(0, m - a):
                s1, s2 = ordn[b], ordn[b + 1]
                v1 = items[s1].L * items[s1].w * items[s1].h
                v2 = items[s2].L * items[s2].w * items[s2].h
                worse = False
                if restric.ordenarPorVolumen:
                    if v1 < v2 - 1e-6:
                        worse = True
                    elif abs(v1 - v2) <= 1e-6 and items[s1].peso < items[s2].peso - 1e-6:
                        worse = True
                else:
                    if items[s1].peso < items[s2].peso - 1e-6:
                        worse = True
                    elif abs(items[s1].peso - items[s2].peso) <= 1e-6 and v1 < v2:
                        worse = True
                if worse:
                    ordn[b], ordn[b + 1] = ordn[b + 1], ordn[b]

    if restric.completarBloque:
        # FASE 1: cada SKU entero, o se revierte y se pospone
        for si in ordn:
            if items[si].qty <= 0:
                continue
            bak_est, bak_np = est.copia(), len(placed)
            bak_u, bak_v, bak_q = acum["unid"], acum["vol"], items[si].qty
            _colocar_columnas_sku(items[si], cL, cW, ch, restric, est, placed, acum, 0)
            if items[si].qty > 0:                         # no cupo entero -> revertir
                est = bak_est
                del placed[bak_np:]
                acum["unid"], acum["vol"], items[si].qty = bak_u, bak_v, bak_q
        # FASE 2: partir UN solo SKU para cerrar el hueco
        for si in ordn:
            if items[si].qty <= 0:
                continue
            q_antes = items[si].qty
            _colocar_columnas_sku(items[si], cL, cW, ch, restric, est, placed, acum, 0)
            if items[si].qty < q_antes:
                break
    else:
        suc_prev, fin_p, fin_pp, x_min_suc = "", 0, 0, 0
        for si in ordn:
            if items[si].qty <= 0:
                continue
            if restric.bloquePorSuc and items[si].suc != suc_prev:
                if suc_prev != "":
                    fin_this = _frontera_x(est.hm)
                    fin_pp, fin_p = fin_p, fin_this
                x_min_suc = fin_pp
                suc_prev = items[si].suc
            _colocar_columnas_sku(items[si], cL, cW, ch, restric, est, placed, acum, x_min_suc)


def pack(items: list[Item], box: Box, restric: Restric, placed: list[Placement]) -> int:
    """CubCore_Pack: empaca UN camión desde cero. Devuelve unidades colocadas."""
    pendientes = [it for it in items if it.qty > 0]
    if len(pendientes) == 1:
        # Un solo producto: se calcula exacto, sin grilla (así se llega al máximo real)
        return carga_mono_exacta(pendientes[0], box, restric, placed)
    acum = {"unid": 0, "vol": 0.0}
    meter_en_camion(box.L, box.w, box.h, items, 0, len(items) - 1, restric, placed, acum)
    return acum["unid"]


TOL_CM = 0.01      # tolerancia de la capacidad: milímetros, no medio centímetro


def capacidad_mono(L: float, w: float, h: float, box: Box, apilable: bool) -> tuple[int, int, int]:
    """Columnas, filas y niveles de un solo producto en un contenedor, con medidas reales."""
    if L <= 0 or w <= 0 or h <= 0 or L > box.L + TOL_CM or w > box.w + TOL_CM:
        return 0, 0, 0
    columnas = int((box.L + TOL_CM) // L)
    filas = int((box.w + TOL_CM) // w)
    niveles = max(int((box.h + TOL_CM) // h), 1) if apilable else 1
    return columnas, filas, niveles


def carga_mono_exacta(it: Item, box: Box, restric: Restric, placed: list[Placement]) -> int:
    """Carga de un solo producto: filas y columnas con centímetros reales, sin redondear.

    El heightmap trabaja en celdas de 1 o 2 cm y redondea cada caja hacia arriba, así que
    con un único producto perdía unidades. Aquí se calcula igual que EasyCargo (y que la
    columna Máx Camión de la Base de Medidas) y se emiten las mismas colocaciones.
    """
    columnas, filas, niveles = capacidad_mono(it.L, it.w, it.h, box, it.apilable)
    if columnas < 1 or filas < 1 or niveles < 1:
        return 0
    vol_u = it.L * it.w * it.h / 1_000_000.0
    puestas = 0
    # Mismo orden de llenado que el motor: primero a lo ancho (y), después avanza en x
    for c in range(columnas):
        for f in range(filas):
            if it.qty <= 0:
                return puestas
            n = min(niveles, it.qty)
            if restric.topeUnidades > 0:
                n = min(n, max(restric.topeUnidades - puestas, 0))
            if n <= 0:
                return puestas
            placed.append(Placement(cod=it.cod, desc=it.desc, ped=it.ped, container=0, fila=it.fila,
                                    x=c * it.L, y=f * it.w, z=0.0, oL=it.L, oW=it.w, oH=it.h,
                                    n=n, nivel=0, volM3=n * vol_u, peso=n * it.peso, suc=it.suc))
            it.qty -= n
            puestas += n
    return puestas


def cascada(items: list[Item], boxes: list[Box], restric: Restric,
            placed: list[Placement]) -> tuple[int, list[int]]:
    """CubCore_Cascada: multi-camión chico->grande. Devuelve (nCont, contBox) con
    contBox[c] = índice 0-based del box usado por el camión c (1..nCont)."""
    i_ch, i_gr = 0, len(boxes) - 1
    n_cont = 0
    cont_box = [0]                     # cont_box[1..n]; índice 0 sin uso (como el VBA)
    forzar_grande = False
    while _unid_restante(items) > 0:
        if forzar_grande:
            usar = i_gr
        else:
            vol_rest = vol_restante_items(items)
            usar = i_ch if vol_rest <= boxes[i_ch].vol_m3 * 0.92 else i_gr
        antes = len(placed)
        col = pack(items, boxes[usar], restric, placed)
        if col == 0:
            if usar == i_gr:
                break
            forzar_grande = True
        else:
            n_cont += 1
            cont_box.append(usar)
            for p in placed[antes:]:
                p.container = n_cont
            forzar_grande = False
        if n_cont > 1000:
            break
    return n_cont, cont_box


def vol_restante_items(items: list[Item]) -> float:
    return sum(it.qty * it.L * it.w * it.h / 1_000_000.0 for it in items if it.qty > 0)


def _unid_restante(items: list[Item]) -> int:
    return sum(it.qty for it in items)


# ---------------------------------------------------------------------------
# Geometría interna
# ---------------------------------------------------------------------------
def _colocar_columnas_sku(it: Item, cL: float, cW: float, ch: float, restric: Restric,
                          est: _Estado, placed: list[Placement], acum: dict, x_min_cell: int):
    vol_u = it.L * it.w * it.h / 1_000_000.0
    while it.qty > 0:
        if restric.topeUnidades > 0 and acum["unid"] >= restric.topeUnidades:
            break
        if restric.motorBestFit:
            r = _mejor_colocacion_bf(it, ch, restric, est, x_min_cell)
        else:
            r = _mejor_colocacion(it, ch, restric, est)
        if r is None:
            break
        bx, by, bz, bOL, bOW, bOH, bcx, bcy = r
        if it.apilable and restric.usaApilable:
            cap_z = vb_int((ch - bz + EPS) / bOH)
        else:
            cap_z = 1
        cap_z = max(cap_z, 1)
        cap_z = min(cap_z, it.qty)
        if restric.topeUnidades > 0 and acum["unid"] + cap_z > restric.topeUnidades:
            cap_z = restric.topeUnidades - acum["unid"]
        if cap_z <= 0:
            break
        z_top = bz + cap_z * bOH
        est.hm[bx:bx + bcx, by:by + bcy] = z_top
        est.pesoTop[bx:bx + bcx, by:by + bcy] = it.peso
        est.sopTop[bx:bx + bcx, by:by + bcy] = it.apilable
        est.invalidar_franjas(bx, bx + bcx)
        placed.append(Placement(
            cod=it.cod, desc=it.desc, ped=it.ped, container=0, fila=it.fila,
            x=bx * CELL, y=by * CELL, z=bz, oL=bOL, oW=bOW, oH=bOH, n=cap_z,
            nivel=0 if bz <= EPS else 1, volM3=cap_z * vol_u, peso=cap_z * it.peso, suc=it.suc))
        acum["unid"] += cap_z
        acum["vol"] += cap_z * vol_u
        it.qty -= cap_z
        if not restric.motorBestFit:
            _agregar_cand(est, bx + bcx, by)
            _agregar_cand(est, bx, by + bcy)
            _agregar_cand(est, bx, by)
            _podar_cand(est, ch)


def _orientaciones(L: float, w: float, h: float, inc: bool, rot: bool) -> list[tuple]:
    oris = [(L, w, h)]
    if rot and w != L:
        oris.append((w, L, h))
    if inc:
        oris.append((L, h, w))
        oris.append((h, L, w))
        if rot:
            oris.append((w, h, L))
            oris.append((h, w, L))
    return oris


def _soporte_ok(it: Item, restric: Restric, est: _Estado, gx: int, gy: int, cx: int, cy: int,
                z: float) -> bool:
    """Soporte >= 70%, todo lo de abajo apilable, no pesado sobre liviano."""
    if (not it.apilable) and z > EPS:
        return False
    if z <= EPS:
        return True
    hm = est.hm[gx:gx + cx, gy:gy + cy]
    apoya = np.abs(hm - z) <= EPS
    cnt = hm.size
    onn = int(apoya.sum())
    if cnt == 0 or onn / cnt < 0.7:
        return False
    if restric.usaApilable and not bool(est.sopTop[gx:gx + cx, gy:gy + cy][apoya].all()):
        return False
    if restric.usaPeso:
        min_peso = float(est.pesoTop[gx:gx + cx, gy:gy + cy][apoya].min()) if onn else PISO_PESO
        if it.peso > min_peso + 1e-6:
            return False
    return True


def _mejor_colocacion(it: Item, ch: float, restric: Restric, est: _Estado):
    """MejorColocacion: corner-point. Mínimo en (x, z, y)."""
    oris = _orientaciones(it.L, it.w, it.h, restric.permiteInclinar and it.inclinable,
                          restric.permiteRotar and it.rotable)
    found = None
    best = None
    for ix, iy in est.cand:
        for oL, oW, oH in oris:
            cx, cy = ceil_neg_int(oL / CELL), ceil_neg_int(oW / CELL)
            if ix + cx > est.nx or iy + cy > est.ny:
                continue
            z = float(est.hm[ix:ix + cx, iy:iy + cy].max())
            if z + oH > ch + EPS:
                continue
            if not _soporte_ok(it, restric, est, ix, iy, cx, cy, z):
                continue
            kx, ky = ix * CELL, iy * CELL
            better = False
            if best is None:
                better = True
            elif kx < best[0] - EPS:
                better = True
            elif abs(kx - best[0]) <= EPS:
                if z < best[1] - EPS:
                    better = True
                elif abs(z - best[1]) <= EPS and ky < best[2] - EPS:
                    better = True
            if better:
                best = (kx, z, ky)
                found = (ix, iy, z, oL, oW, oH, cx, cy)
    return found


def _suma_ventana(mask: np.ndarray, cx: int, cy: int) -> np.ndarray:
    """Cantidad de celdas True en cada ventana cx x cy (imagen integral)."""
    ii = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int32)
    np.cumsum(np.cumsum(mask, axis=0, dtype=np.int32), axis=1, out=ii[1:, 1:])
    return (ii[cx:, cy:] - ii[:-cx, cy:] - ii[cx:, :-cy] + ii[:-cx, :-cy])


def _max_ventana(a: np.ndarray, k: int, eje: int) -> np.ndarray:
    """Máximo de cada ventana de k celdas seguidas a lo largo de `eje`.

    Mismo resultado que sliding_window_view(...).max(), pero por doblado: cada paso
    combina la ventana con su copia desplazada, así el costo es O(N log k) y no O(N k).
    """
    if k <= 1:
        return a

    def cortar(x, desde, hasta):
        idx = [slice(None)] * x.ndim
        idx[eje] = slice(desde, hasta)
        return x[tuple(idx)]

    m, p = a, 1                              # m[i] = max(a[i : i + p])
    while p * 2 <= k:
        m = np.maximum(cortar(m, 0, m.shape[eje] - p), cortar(m, p, None))
        p *= 2
    if p < k:
        d = k - p
        m = np.maximum(cortar(m, 0, m.shape[eje] - d), cortar(m, d, None))
    return m


def _mejor_colocacion_bf(it: Item, ch: float, restric: Restric, est: _Estado, x_min_cell: int):
    """MejorColocacionBF: best-fit por columna sobre la grilla, sin rotar.

    Orden de búsqueda: gx ascendente, luego gy ascendente; la primera válida gana.
    La grilla se recorre por franjas de gx y se corta en la primera franja con una
    posición válida: en un camión que se va llenando de adelante hacia atrás, casi
    siempre aparece cerca del frente y no hace falta mirar el resto. Dentro de cada
    franja se evalúan todas las posiciones a la vez (soporte, apilabilidad y peso con
    imágenes integrales). El resultado es idéntico a recorrer la grilla completa.
    """
    cx = max(ceil_neg_int(it.L / CELL), 1)
    cy = max(ceil_neg_int(it.w / CELL), 1)
    if cx > est.nx or cy > est.ny:
        return None
    gx0 = max(x_min_cell, 0)
    gx_fin = est.nx - cx + 1                      # posiciones gx válidas: [gx0, gx_fin)
    if gx0 >= gx_fin:
        return None
    # El resultado de una franja depende solo de lo que se pregunta y de las filas que lee
    clave = (cx, cy, it.h, it.apilable, ch, restric.usaApilable, restric.usaPeso,
             it.peso if restric.usaPeso else 0.0)
    if clave not in est.vacias and len(est.vacias) >= 48:
        est.vacias.pop(next(iter(est.vacias)))          # tope: solo es una cache, se puede descartar
    vacias = est.vacias.setdefault(clave, set())
    paso = max(4 * cx, 48)
    a = gx0
    while a < gx_fin:
        b = min(a + paso, gx_fin)
        if (a, b) not in vacias:
            r = _mejor_en_franja(it, ch, restric, est, a, b, cx, cy)
            if r is not None:
                return r
            vacias.add((a, b))
        a = b
    return None


def _mejor_en_franja(it: Item, ch: float, restric: Restric, est: _Estado,
                     a: int, b: int, cx: int, cy: int):
    """Primera posición válida con gx en [a, b), o None. Solo lee las filas que necesita."""
    oH = it.h
    hm = est.hm[a:b + cx - 1]
    rowmax = _max_ventana(hm, cy, 1)                         # (b-a+cx-1, ny-cy+1)
    sub = _max_ventana(rowmax, cx, 0)                        # (b-a, ny-cy+1)
    ok = sub + oH <= ch + EPS
    if not it.apilable:
        ok &= sub <= EPS
    if not ok.any():
        return None

    valido = ok & (sub <= EPS)                    # apoyo en el piso: siempre soporta
    alturas = np.unique(sub[ok & (sub > EPS)])
    if alturas.size:
        cnt = cx * cy
        if alturas.size > 60:                     # demasiadas alturas: cae al chequeo directo
            for gx_rel, gy in np.argwhere(ok):
                gx, gy = a + int(gx_rel), int(gy)
                z = float(sub[gx_rel, gy])
                if _soporte_ok(it, restric, est, gx, gy, cx, cy, z):
                    return (gx, gy, z, it.L, it.w, oH, cx, cy)
            return None
        sop = est.sopTop[a:b + cx - 1]
        peso = est.pesoTop[a:b + cx - 1]
        for z in alturas:
            apoya = hm >= z - EPS                 # z es el máximo de la ventana
            bien = (_suma_ventana(apoya, cx, cy) / cnt) >= 0.7
            # Cada restriccion solo descarta posiciones si existe alguna celda de apoyo que la
            # viole; si no hay ninguna, la suma por ventana es cero en toda la grilla y se omite.
            if restric.usaApilable:
                no_apilable = apoya & ~sop
                if no_apilable.any():
                    bien &= _suma_ventana(no_apilable, cx, cy) == 0
            if restric.usaPeso:
                liviano = apoya & (peso < it.peso - 1e-6)
                if liviano.any():
                    bien &= _suma_ventana(liviano, cx, cy) == 0
            valido |= ok & (sub == z) & bien
    if not valido.any():
        return None
    idx = int(np.argmax(valido))                  # primera en orden gx asc, gy asc
    gx_rel, gy = divmod(idx, valido.shape[1])
    return (a + gx_rel, gy, float(sub[gx_rel, gy]), it.L, it.w, oH, cx, cy)


def _frontera_x(hm: np.ndarray) -> int:
    """FronteraX: 1 + el mayor gx con altura ocupada (0 si está vacío)."""
    ocupado = np.nonzero((hm > 0).any(axis=1))[0]
    return int(ocupado[-1]) + 1 if ocupado.size else 0


def _agregar_cand(est: _Estado, ix: int, iy: int):
    if ix < 0 or iy < 0 or ix >= est.nx or iy >= est.ny:
        return
    if (ix, iy) in est.cand:
        return
    if len(est.cand) >= MAX_CAND:
        return
    est.cand.append((ix, iy))


def _podar_cand(est: _Estado, ch: float):
    est.cand = [(ix, iy) for ix, iy in est.cand
                if 0 <= ix < est.nx and 0 <= iy < est.ny and est.hm[ix, iy] < ch - EPS]
