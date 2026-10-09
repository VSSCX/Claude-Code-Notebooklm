"""Port de Cubicaje_SDA_Stock (etapa 1): bloques, capacidad del pallet y armado de pallets.

Etapas del modo en el VBA:
  1. Lectura + caja master  -> aquí
  2. Capacidad por pallet   -> aquí (SDA_CapMono)
  3. Armado de pallets      -> aquí (mono + remix de pallets flojos)
  4. Validación geométrica, carga a piso y camiones -> siguiente entrega

Conceptos que se conservan del VBA:
- "Caja" = caja master (C + SKU), "Suelta" = unidades que sobran de la caja master,
  "Indiv" = producto suelto cuando no hay caja master o el operador la desactivó con X.
- Un pallet admite como máximo 2 bloques distintos al armarlo (pK >= 2 cierra el pallet).
- Los pallets que quedan por debajo del 60% se deshacen y su contenido se remezcla.
- Un producto que no cabe en el pallet ni sin rotar se marca para ir a piso.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .core import Item, Placement, Restric, meter_en_camion
from .datos import Dims, get_dims_for
from .mda import NO_ENCONTRADO, Posicion
from .vb import clng, vb_int

EPS_SDA = 0.0001
U_SDA = 0.6          # bajo este llenado, el pallet se considera flojo y se remezcla
MAX_BLOQUES_PALLET = 8


def restricciones_sda() -> Restric:
    """Las banderas que fija Cubicaje_SDA_Stock (ojo: aquí sí se reordena por volumen)."""
    return Restric(usaPeso=True, usaApilable=True, permiteRotar=False, permiteInclinar=False,
                   usaTopes=False, topeUnidades=0, ordenarPorVolumen=True, cargarDesdeFondo=True,
                   respetarOrden=False, completarBloque=False, motorBestFit=True, bloquePorSuc=False)


@dataclass
class Bloque:
    """Una unidad de carga: caja master, unidades sueltas o producto individual."""
    cod: str
    desc: str
    tipo: str            # Caja | Suelta | Indiv
    cm_por_caja: int     # unidades dentro de la caja master (1 en los otros tipos)
    n: int               # cantidad de este bloque
    L: float
    w: float
    h: float
    apilable: bool
    rotable: bool
    peso: float
    pedido: str
    sucursal: str = ""        # modos predistribuidos
    cap_pallet: int = 0       # cuántos caben en un pallet mono (SDA_CapMono)
    no_cabe: bool = False     # no entra en el pallet: va a piso
    volumen: float = 0.0

    @property
    def unidades(self) -> int:
        """Unidades de producto que representa el bloque (la caja master trae varias)."""
        return self.n * max(self.cm_por_caja, 1)


@dataclass
class Pallet:
    """Bloques que van en un pallet: lista de (índice de bloque, cantidad)."""
    contenido: list[tuple[int, int]] = field(default_factory=list)
    frac: float = 0.0        # llenado 0..1 respecto de la capacidad mono de cada bloque
    sucursal: str = ""       # modos predistribuidos
    tipo: str = ""           # Mono-Suc | Mono-SKU | Mix

    @property
    def k(self) -> int:
        return len(self.contenido)


def construir_bloques(posiciones: list[Posicion], cache: dict[str, Dims], usa_caja_master: bool,
                      pasa_filtro=None) -> tuple[list[Bloque], list[str], list[str]]:
    """Lee 02_Posiciones y arma los bloques, partiendo por caja master cuando corresponde."""
    bloques: list[Bloque] = []
    sin_medidas: list[str] = []
    sin_caja: list[str] = []
    for p in posiciones:
        sk = str(p.sku).strip()
        if not sk:
            continue
        if pasa_filtro is not None and not pasa_filtro(sk):
            continue
        qty = clng(p.carga) if isinstance(p.carga, (int, float)) else 0
        if qty <= 0:
            continue
        desc = str(p.desc).strip()
        if desc == NO_ENCONTRADO:
            continue
        ped = str(p.pedido).strip() or f"_row{p.fila}"
        sin_cm = str(p.cm_override).strip().upper() == "X"

        hecho = False
        if usa_caja_master and not sin_cm:
            dc = get_dims_for(cache, "C" + sk)
            if dc is not None:
                cmp_ = dc.piezas if dc.piezas > 0 else 1
                cajas, sueltas = divmod(qty, cmp_)
                if cajas > 0:
                    bloques.append(Bloque(cod=sk, desc=desc, tipo="Caja", cm_por_caja=cmp_, n=cajas,
                                          L=dc.L, w=dc.w, h=dc.h, apilable=dc.apilable, rotable=False,
                                          peso=dc.peso, pedido=ped))
                if sueltas > 0:
                    ds = get_dims_for(cache, sk)
                    if ds is not None:
                        bloques.append(Bloque(cod=sk, desc=desc, tipo="Suelta", cm_por_caja=1,
                                              n=sueltas, L=ds.L, w=ds.w, h=ds.h,
                                              apilable=ds.apilable, rotable=False, peso=ds.peso,
                                              pedido=ped))
                hecho = True
        if not hecho:
            d = get_dims_for(cache, sk)
            if d is None:
                if sk not in sin_medidas:
                    sin_medidas.append(sk)
                continue
            bloques.append(Bloque(cod=sk, desc=desc, tipo="Indiv", cm_por_caja=1, n=qty,
                                  L=d.L, w=d.w, h=d.h, apilable=d.apilable, rotable=False,
                                  peso=d.peso, pedido=ped))
            if usa_caja_master and not sin_cm and sk not in sin_caja:
                sin_caja.append(sk)
    return bloques, sin_medidas, sin_caja


def orientar_pallet(pal_L: float, pal_W: float, modo: str, bloques: list = None,
                    restric: Restric = None, pal_H: float = 0) -> tuple[float, float]:
    """Cómo se acomoda el pallet respecto del eje largo del empaque.

    - "excel": como el VBA, el ancho del pallet hace de largo (lo que se venía usando).
    - "largo": el largo del pallet hace de largo.
    - "auto":  se prueban las dos y gana la que permite cargar más unidades.
    Importa porque los productos no rotan: con 29 cm de frente caben 3 en 100 cm y 4 en 120.
    """
    m = (modo or "excel").lower()
    if m == "largo":
        return pal_W, pal_L
    if m == "auto" and bloques and restric is not None:
        def total(a, b):
            t = 0
            for x in bloques:
                it = Item(cod="X", desc="X", L=x.L, w=x.w, h=x.h, peso=x.peso, apilable=x.apilable,
                          rotable=x.rotable, inclinable=False, qty=1500, fila=1, ped="X")
                acum = {"unid": 0, "vol": 0.0}
                meter_en_camion(a, b, pal_H, [it], 0, 0, restric, [], acum)
                t += acum["unid"] * max(x.n, 1)
            return t
        return (pal_L, pal_W) if total(pal_L, pal_W) >= total(pal_W, pal_L) else (pal_W, pal_L)
    return pal_L, pal_W


def cap_mono(b: Bloque, pal_L: float, pal_W: float, pal_H: float, restric: Restric = None) -> int:
    """Cuántos bloques iguales caben en un pallet vacío, con aritmética exacta.

    Sin grilla: el heightmap trabaja en celdas de 1 o 2 cm y eso redondeaba las medidas
    hacia arriba (32,5 cm pasaba a 34 y dejaba de caber tres veces en 100 cm). Aquí se
    usan los centímetros reales, igual que EasyCargo:
        columnas = piso(largo del pallet / largo de la caja)
        filas    = piso(ancho del pallet / ancho de la caja)
        niveles  = piso(alto del pallet / alto de la caja), o 1 si el producto no se apila
    Un producto que no se apila no queda limitado por el alto del pallet (va igual, solo
    que en un nivel), que es lo que hace EasyCargo con los refrigeradores altos.
    """
    if b.L <= 0 or b.w <= 0 or b.h <= 0:
        return 0
    # Mismos ejes que usa el motor al llenar el pallet: el largo de la caja va sobre pal_W
    from .core import TOL_CM
    if b.L > pal_W + TOL_CM or b.w > pal_L + TOL_CM:
        return 0                     # no entra en la huella del pallet: irá a piso
    columnas = int((pal_W + TOL_CM) // b.L)
    filas = int((pal_L + TOL_CM) // b.w)
    niveles = max(int((pal_H + TOL_CM) // b.h), 1) if b.apilable else 1
    return max(columnas * filas * niveles, 0)


def calcular_capacidades(bloques: list[Bloque], pal_L: float, pal_W: float, pal_H: float,
                         restric: Restric, cache: dict = None, usar_tabla: bool = False) -> None:
    """usar_tabla: toma la columna "Máx Pallet" de la Base de Medidas (la de EasyCargo)
    en vez de calcular la capacidad con geometría."""
    from .datos import get_dims_for
    for b in bloques:
        tope = 0
        if usar_tabla and cache is not None:
            clave = ("C" + b.cod) if b.tipo == "Caja" else b.cod
            d = get_dims_for(cache, clave)
            tope = int(getattr(d, "max_pallet", 0) or 0) if d else 0
        b.cap_pallet = tope or cap_mono(b, pal_L, pal_W, pal_H, restric)
        if b.cap_pallet < 1:
            b.no_cabe = True        # no entra en el pallet: irá a piso
            b.cap_pallet = 1
        b.volumen = b.L * b.w * b.h


def ordenar_por_volumen(bloques: list[Bloque]) -> None:
    """Burbuja por volumen descendente (SDA_SwapBloque mueve el bloque completo)."""
    n = len(bloques)
    for a in range(n - 1):
        for b in range(n - 1 - a):
            if bloques[b].volumen < bloques[b + 1].volumen:
                bloques[b], bloques[b + 1] = bloques[b + 1], bloques[b]


def armar_pallets(bloques: list[Bloque]) -> tuple[list[Pallet], list[tuple[int, int]]]:
    """Arma los pallets y devuelve también los bloques forzados a piso (índice, cantidad)."""
    restante = [b.n for b in bloques]
    piso: list[tuple[int, int]] = []
    pallets: list[Pallet] = []
    actual: Pallet | None = None
    i = 0
    while i < len(bloques):
        if restante[i] <= 0:
            i += 1
            continue
        if bloques[i].no_cabe:
            piso.append((i, restante[i]))
            restante[i] = 0
            i += 1
            continue
        if actual is None:
            actual = Pallet()
            pallets.append(actual)
        ya = next((k for k, (bi, _) in enumerate(actual.contenido) if bi == i), None)
        if actual.k >= 2 and ya is None:
            actual = None                      # el pallet ya tiene dos bloques: se cierra
            continue
        espacio = 1.0 - actual.frac
        caben = vb_int(espacio * bloques[i].cap_pallet + EPS_SDA)
        m = min(restante[i], caben)
        if m > 0:
            if ya is None:
                actual.contenido.append((i, 0))
                ya = actual.k - 1
            bi, n = actual.contenido[ya]
            actual.contenido[ya] = (bi, n + m)
            actual.frac += m / bloques[i].cap_pallet
            restante[i] -= m
        if restante[i] > 0:
            actual = None                      # no cupo todo: se abre otro pallet
        else:
            i += 1
    return pallets, piso


def armar_pallets_por_producto(bloques: list[Bloque]) -> tuple[list[Pallet], list[tuple[int, int]]]:
    """Clientes con la restricción «un producto por pallet» (FALABELLA, EASY): cada SKU arma sus propios pallets y
    nada se mezcla con otro SKU, aunque el pallet quede con poca carga. Las cajas master y las unidades sueltas del
    MISMO SKU sí pueden compartir pallet (es el mismo producto). Un SKU puede ocupar más de un pallet."""
    por_cod: dict[str, list[int]] = {}
    for i, b in enumerate(bloques):
        por_cod.setdefault(b.cod, []).append(i)
    pallets: list[Pallet] = []
    piso: list[tuple[int, int]] = []
    for idx in por_cod.values():
        sub = [bloques[i] for i in idx]
        pals, pis = armar_pallets(sub)
        for p in pals:
            p.contenido = [(idx[bi], n) for bi, n in p.contenido]
            p.tipo = "Mono"
            pallets.append(p)
        piso += [(idx[bi], n) for bi, n in pis]
    return pallets, piso


def remezclar_flojos(pallets: list[Pallet], bloques: list[Bloque]) -> list[Pallet]:
    """Deshace los pallets con menos del 60% y reparte su contenido en pallets mix."""
    pool: list[list] = []          # [índice de bloque, unidades]
    flojos = set()
    for idx, p in enumerate(pallets):
        if p.frac < U_SDA - EPS_SDA:
            flojos.add(idx)
            for bi, n in p.contenido:
                fila = next((x for x in pool if x[0] == bi), None)
                if fila is None:
                    fila = [bi, 0]
                    pool.append(fila)
                fila[1] += n
    if not pool:
        return [p for i, p in enumerate(pallets) if i not in flojos and p.k > 0]

    # más lleno primero (fracción respecto de su capacidad mono)
    n = len(pool)
    for x in range(n - 1):
        for y in range(n - 1 - x):
            f1 = pool[y][1] / bloques[pool[y][0]].cap_pallet
            f2 = pool[y + 1][1] / bloques[pool[y + 1][0]].cap_pallet
            if f1 < f2:
                pool[y], pool[y + 1] = pool[y + 1], pool[y]

    base_mix = len(pallets)
    for bi, pend in pool:
        for pp in range(base_mix, len(pallets)):        # primero, los pallets mix ya abiertos
            p = pallets[pp]
            if p.k >= MAX_BLOQUES_PALLET:
                continue
            caben = vb_int((1.0 - p.frac) * bloques[bi].cap_pallet + EPS_SDA)
            if caben <= 0:
                continue
            m = min(pend, caben)
            p.contenido.append((bi, m))
            p.frac += m / bloques[bi].cap_pallet
            pend -= m
            if pend <= 0:
                break
        while pend > 0:                                  # y si sobra, pallets nuevos
            m = min(pend, bloques[bi].cap_pallet)
            pallets.append(Pallet(contenido=[(bi, m)], frac=m / bloques[bi].cap_pallet))
            pend -= m
    return [p for i, p in enumerate(pallets) if i not in flojos and p.k > 0]


# ===========================================================================
# Etapa 4: validación geométrica, camiones, carga a piso y salida
# ===========================================================================
CAP_RAMPLA, CAP_CAM50 = 30, 12          # pallets por vehículo
RAMPLA = ("Rampla", 1540.0, 245.0, 235.0)
CAMION50 = ("Camion 50", 620.0, 244.0, 230.0)


def usar_camiones(rampla: tuple, camion50: tuple) -> None:
    """Cambia las medidas de los vehículos (nombre, largo, ancho, alto en cm). Las fija Configuración antes de cubicar."""
    global RAMPLA, CAMION50
    RAMPLA, CAMION50 = tuple(rampla), tuple(camion50)
TARIMA = 14.5                            # alto de la tarima del pallet
GAPX, GAPY, GAP_PISO = 8.0, 5.0, 8.0
LARGO_MIN_PISO = 60.0


@dataclass
class Vehiculo:
    numero: int
    tipo: str
    L: float
    w: float
    h: float
    pal_desde: int          # 1-based, inclusivo
    pal_hasta: int


@dataclass
class FilaSDA:
    """Una fila de 04_CubicajeSDA."""
    vehiculo: int
    tipo_vehiculo: str
    pallet: int             # 0 = carga a piso
    sku: str
    descripcion: str
    cajas: int
    bultos: int
    unidades: int
    tipo: str               # Mono | Mix | Piso
    pedido: str
    sucursal: str = ""


def asignar_vehiculos(total_pallets: int) -> list[Vehiculo]:
    """AsignarVeh: rampla si quedan más de 12 pallets, si no camión 50."""
    vehiculos: list[Vehiculo] = []
    restante, usados = total_pallets, 0
    while restante > 0:
        if restante > CAP_CAM50:
            tipo, L, w, h = RAMPLA
            cap = min(restante, CAP_RAMPLA)
        else:
            tipo, L, w, h = CAMION50
            cap = restante
        vehiculos.append(Vehiculo(numero=len(vehiculos) + 1, tipo=tipo, L=L, w=w, h=h,
                                  pal_desde=usados + 1, pal_hasta=usados + cap))
        usados += cap
        restante -= cap
    return vehiculos


def _items_de_pallet(pallet: Pallet, bloques: list[Bloque]) -> list[Item]:
    return [Item(cod=bloques[bi].cod, desc=bloques[bi].desc, L=bloques[bi].L, w=bloques[bi].w,
                 h=bloques[bi].h, peso=bloques[bi].peso, apilable=bloques[bi].apilable,
                 rotable=bloques[bi].rotable, inclinable=False, qty=n, fila=bi,
                 ped=bloques[bi].pedido)
            for bi, n in pallet.contenido if n > 0]


def _cubicar_pallet(items: list[Item], pal_L: float, pal_W: float, pal_H: float,
                    restric: Restric) -> tuple[list[Placement], int]:
    acum = {"unid": 0, "vol": 0.0}
    plc: list[Placement] = []
    if items:
        meter_en_camion(pal_W, pal_L, pal_H, items, 0, len(items) - 1, restric, plc, acum)
    return plc, acum["unid"]


def validar_pallets(pallets: list[Pallet], bloques: list[Bloque], pal_L: float, pal_W: float,
                    pal_H: float, restric: Restric, misma_sucursal: bool = False,
                    por_producto: bool = False) -> tuple[list[Pallet], dict[int, list[Placement]]]:
    """Comprueba con el motor que cada pallet realmente cierre, y reubica lo que sobra.

    Reglas del VBA (las que costaron los arreglos de julio):
    - Se guardan las colocaciones de la validación y se reutilizan después, en vez de
      volver a cubicar (si no, el volcado y la validación no coinciden).
    - Si un bloque no entra completo, lo que sobra se encola.
    - Un bloque con 0 colocado dentro de un pallet mix se saca entero.
    - Con por_producto, lo encolado solo se reubica en pallets del mismo producto.
    - Lo encolado se reubica en pallets con hueco REAL (se recubica el pallet completo y
      solo se acepta si entra TODO); si ninguno lo admite, recién ahí se abre pallet nuevo.
    """
    placements: dict[int, list[Placement]] = {}
    cola: list[tuple[int, int]] = []
    n_originales = len(pallets)

    for idx in range(n_originales):
        p = pallets[idx]
        items = _items_de_pallet(p, bloques)
        if not items:
            continue
        plc, _ = _cubicar_pallet(items, pal_L, pal_W, pal_H, restric)
        placements[idx] = plc
        for k, (bi, n) in enumerate(list(p.contenido)):
            if n <= 0:
                continue
            colocado = sum(x.n for x in plc if x.fila == bi)
            sobra = n - colocado
            if sobra <= 0:
                continue
            if colocado > 0:
                p.contenido[k] = (bi, colocado)
                cola.append((bi, sobra))
            elif p.k > 1:                      # en un pallet mix, el bloque sale entero
                p.contenido[k] = (bi, 0)
                cola.append((bi, sobra))

    for bi, qty in cola:
        if qty <= 0:
            continue
        colocado = False
        for idx, p in enumerate(pallets):
            if p.frac >= 1.0 or p.k < 1:
                continue
            if misma_sucursal and p.sucursal != bloques[bi].sucursal:
                continue          # en predistribuido, el sobrante no cruza de sucursal
            if por_producto and any(bloques[b].cod != bloques[bi].cod for b, _ in p.contenido):
                continue          # un producto por pallet: el sobrante no se mezcla con otro producto
            prueba = Pallet(contenido=[(b, n + qty if b == bi else n) for b, n in p.contenido],
                            frac=p.frac)
            if not any(b == bi for b, _ in p.contenido):
                if p.k >= MAX_BLOQUES_PALLET:
                    continue
                prueba.contenido = list(p.contenido) + [(bi, qty)]
            items = _items_de_pallet(prueba, bloques)
            objetivo = sum(n for _, n in prueba.contenido)
            plc, puestas = _cubicar_pallet(items, pal_L, pal_W, pal_H, restric)
            if puestas >= objetivo:            # solo si entra TODO
                p.contenido = prueba.contenido
                p.frac += qty / bloques[bi].cap_pallet
                placements[idx] = plc
                colocado = True
                break
        if not colocado:
            nuevo = Pallet(contenido=[(bi, qty)], frac=qty / bloques[bi].cap_pallet,
                           sucursal=bloques[bi].sucursal if misma_sucursal else "",
                           tipo="Mono-Suc" if misma_sucursal else ("Mono" if por_producto else ""))
            pallets.append(nuevo)
            items = _items_de_pallet(nuevo, bloques)
            plc, _ = _cubicar_pallet(items, pal_L, pal_W, pal_H, restric)
            placements[len(pallets) - 1] = plc

    finales, place_final = [], {}
    for idx, p in enumerate(pallets):          # se descartan los pallets que quedaron vacíos
        if sum(n for _, n in p.contenido) > 0:
            place_final[len(finales)] = placements.get(idx, [])
            finales.append(p)
    return finales, place_final


def grilla_simple(items: list[Item], pal_L: float, pal_W: float) -> list[Placement]:
    """Colocación en grilla, como el respaldo del VBA cuando el motor no devuelve nada.
    Se usa cuando la capacidad viene de la tabla: el dibujo es aproximado, la cantidad exacta."""
    plc: list[Placement] = []
    for it in items:
        cols = max(int(pal_W / it.L) if it.L > 0 else 1, 1)
        col = fila = 0
        z = 0.0
        for _ in range(it.qty):
            plc.append(Placement(cod=it.cod, desc=it.desc, ped=it.ped, container=0, fila=it.fila,
                                 x=col * it.L, y=fila * it.w, z=z, oL=it.L, oW=it.w, oH=it.h,
                                 n=1, nivel=0 if z <= 0 else 1, volM3=it.L * it.w * it.h / 1e6,
                                 peso=it.peso, suc=it.suc))
            col += 1
            if col >= cols:
                col = 0
                fila += 1
                if (fila + 1) * it.w > pal_L:
                    fila = 0
                    z += it.h
    return plc


def ubicar_pallets(pallets: list[Pallet], placements: dict[int, list[Placement]],
                   bloques: list[Bloque], vehiculos: list[Vehiculo], pal_L: float,
                   pal_W: float, girar: bool = False) -> tuple[list[Placement], list[FilaSDA], dict]:
    """Coloca cada pallet en su camión (2 columnas frontis-a-fondo) y arma las filas de 04.

    girar: las cajas se acomodaron a lo largo del pallet (120), pero el pallet viaja con
    ese lado cruzado al camión, así que sus coordenadas rotan 90°.
    """
    colocados: list[Placement] = []
    filas: list[FilaSDA] = []
    geo: dict[int, dict] = {}      # pallet visible -> {veh, x, y}
    for i, p in enumerate(pallets):
        n_pal = i + 1
        veh = next((v for v in vehiculos if v.pal_desde <= n_pal <= v.pal_hasta), vehiculos[0])
        idx_en_veh = n_pal - veh.pal_desde
        fila, col = divmod(idx_en_veh, 2)
        cap_v = veh.pal_hasta - veh.pal_desde + 1
        n_filas = max((cap_v + 1) // 2, 1)
        gap_x = GAPX
        if n_filas > 1:
            gap_x = min(max((veh.L - n_filas * pal_W) / (n_filas - 1), 0.0), GAPX)
        x0 = fila * (pal_W + gap_x)
        # El VBA deja 5 cm entre las dos columnas de pallets; en un camión angosto eso
        # dibuja el segundo pallet fuera del camión (2 x 120 + 5 = 245 > 244). Se achica
        # la separación al espacio real: cambia solo el dibujo, no la carga.
        gap_y = min(GAPY, max(veh.w - 2 * pal_L, 0.0))
        mar_y = max((veh.w - 2 * pal_L - gap_y) / 2.0, 0.0)
        y0 = mar_y + col * (pal_L + gap_y)
        tipo_pal = p.tipo or ("Mono" if p.k == 1 else "Mix")
        geo[n_pal] = {"veh": veh.numero, "x": x0, "y": y0}
        for bi, n in p.contenido:
            if n > 0:
                b = bloques[bi]
                filas.append(FilaSDA(vehiculo=veh.numero, tipo_vehiculo=veh.tipo, pallet=n_pal,
                                     sku=b.cod, descripcion=b.desc, cajas=n,
                                     bultos=n, unidades=n * max(b.cm_por_caja, 1),
                                     tipo=tipo_pal, pedido=b.pedido))
        for pl in placements.get(i, []):
            b = bloques[pl.fila] if 0 <= pl.fila < len(bloques) else None
            px, py, poL, poW = (pl.y, pl.x, pl.oW, pl.oL) if girar else (pl.x, pl.y, pl.oL, pl.oW)
            colocados.append(Placement(
                cod=(("C" + b.cod) if b and b.tipo == "Caja" else (b.cod if b else pl.cod)),
                desc=(b.desc if b else pl.desc), ped=pl.ped, container=veh.numero, fila=pl.fila,
                x=x0 + px, y=y0 + py, z=TARIMA + pl.z, oL=poL, oW=poW, oH=pl.oH,
                n=pl.n, nivel=pl.nivel, volM3=pl.volM3, peso=pl.peso, suc=pl.suc,
                pallet=n_pal))
    return colocados, filas, geo


def cargar_piso(piso: list[tuple[int, int]], bloques: list[Bloque], vehiculos: list[Vehiculo],
                geo: dict, pal_W: float, restric_piso: Restric) -> tuple[list[Placement], list[FilaSDA], list[Vehiculo]]:
    """Los productos que no caben en pallet van a piso: primero detrás de los pallets de cada
    camión, y si sobra, en ramplas nuevas."""
    items = [Item(cod=bloques[bi].cod, desc=bloques[bi].desc, L=bloques[bi].L, w=bloques[bi].w,
                  h=bloques[bi].h, peso=bloques[bi].peso, apilable=bloques[bi].apilable,
                  rotable=False, inclinable=False, qty=n, fila=bi, ped=bloques[bi].pedido)
             for bi, n in piso if n > 0]
    colocados: list[Placement] = []
    filas: list[FilaSDA] = []
    if not items:
        return colocados, filas, vehiculos

    def _agregar(v: Vehiculo, plc: list[Placement], dx: float):
        for pl in plc:
            b = bloques[pl.fila] if 0 <= pl.fila < len(bloques) else None
            colocados.append(Placement(
                cod=(("C" + b.cod) if b and b.tipo == "Caja" else pl.cod), desc=pl.desc, ped=pl.ped,
                container=v.numero, fila=pl.fila, x=dx + pl.x, y=pl.y, z=pl.z, oL=pl.oL, oW=pl.oW,
                oH=pl.oH, n=pl.n, nivel=pl.nivel, volM3=pl.volM3, peso=pl.peso, suc=pl.suc))
            if b is not None:
                filas.append(FilaSDA(vehiculo=v.numero, tipo_vehiculo=v.tipo, pallet=0, sku=b.cod,
                                     descripcion=b.desc, cajas=pl.n, bultos=pl.n,
                                     unidades=pl.n * max(b.cm_por_caja, 1), tipo="Piso",
                                     pedido=b.pedido))

    for v in list(vehiculos):                       # 1) detrás de los pallets ya cargados
        if sum(it.qty for it in items) <= 0:
            break
        x_fin = max((g["x"] + pal_W for g in geo.values() if g["veh"] == v.numero), default=0.0)
        if x_fin <= 0:
            continue
        largo = v.L - x_fin - GAP_PISO
        if largo < LARGO_MIN_PISO:
            continue
        acum = {"unid": 0, "vol": 0.0}
        plc: list[Placement] = []
        meter_en_camion(largo, v.w, v.h, items, 0, len(items) - 1, restric_piso, plc, acum)
        _agregar(v, plc, x_fin + GAP_PISO)

    while sum(it.qty for it in items) > 0:          # 2) ramplas nuevas
        tipo, L, w, h = RAMPLA
        v = Vehiculo(numero=len(vehiculos) + 1, tipo=tipo, L=L, w=w, h=h, pal_desde=0, pal_hasta=-1)
        vehiculos.append(v)
        acum = {"unid": 0, "vol": 0.0}
        plc = []
        meter_en_camion(v.L, v.w, v.h, items, 0, len(items) - 1, restric_piso, plc, acum)
        if not plc:
            break
        _agregar(v, plc, 0.0)
    return colocados, filas, vehiculos


def restricciones_piso() -> Restric:
    """Las que usa el VBA para la carga a piso: respeta el orden y no reordena."""
    return Restric(usaPeso=True, usaApilable=True, permiteRotar=False, permiteInclinar=False,
                   usaTopes=False, topeUnidades=0, ordenarPorVolumen=False, cargarDesdeFondo=True,
                   respetarOrden=True, completarBloque=False, motorBestFit=True, bloquePorSuc=False)


def cubicaje_sda_stock(posiciones: list[Posicion], cache: dict[str, Dims], pal_L: float,
                       pal_W: float, pal_H: float, usa_caja_master: bool, pedidos: list[str],
                       pasa_filtro=None, cam_offset: int = 0, orientacion: str = "excel",
                       capacidad: str = "geometria", kits: dict | None = None, kits_mezclar: bool = False,
                       por_producto: bool = False):
    """Modo SDA Stock completo: bloques -> pallets -> camiones -> piso -> salida."""
    from .kits import armar_pallets_kit, separar_kits
    from .mda import Camion, Fila03, Resultado
    from .vb import vb_round

    res = Resultado(modo="SDA STOCK")
    restric = restricciones_sda()
    posiciones, lineas_kit = separar_kits(posiciones, kits, pasa_filtro)
    bloques, sin_medidas, sin_caja = construir_bloques(posiciones, cache, usa_caja_master, pasa_filtro)
    res.sin_medidas = sin_medidas
    res.no_encontrados = [p.sku for p in posiciones if str(p.desc).strip() == NO_ENCONTRADO]
    if sin_caja:
        res.avisos.append("Sin caja master, cubicados individuales: " + ", ".join(sin_caja))
    if not bloques and not lineas_kit:
        res.avisos.append("Sin SKUs cubicables en SDA Stock.")
        return res

    tabla = capacidad == "tabla"
    # La orientación es solo para acomodar las CAJAS dentro del pallet. La estiba de los
    # pallets en el camión no cambia: 120 cm a lo ancho (2 columnas) y 100 a lo largo.
    pack_L, pack_W = orientar_pallet(pal_L, pal_W, orientacion, bloques, restric, pal_H)
    calcular_capacidades(bloques, pack_L, pack_W, pal_H, restric, cache, tabla)
    ordenar_por_volumen(bloques)
    if por_producto:                    # restricción del cliente: cada producto en sus pallets, sin remezclar
        pallets, piso = armar_pallets_por_producto(bloques)
        res.avisos.append("Un producto por pallet (regla del cliente): no se mezclan productos, "
                          "aunque algún pallet quede con poca carga.")
    else:
        pallets, piso = armar_pallets(bloques)
        pallets = remezclar_flojos(pallets, bloques)
    if tabla:
        # La capacidad la manda la Base de Medidas: no se revalida con geometría
        pallets = [p for p in pallets if sum(n for _, n in p.contenido) > 0]
        placements = {i: grilla_simple(_items_de_pallet(p, bloques), pack_L, pack_W)
                      for i, p in enumerate(pallets)}
    else:
        pallets, placements = validar_pallets(pallets, bloques, pack_L, pack_W, pal_H, restric,
                                              por_producto=por_producto)
    if lineas_kit:                      # los kits van en pallets propios, completos
        kp, kplc, kpiso, kav, ksm = armar_pallets_kit(lineas_kit, cache, bloques, pack_L, pack_W, pal_H, restric,
                                                      mezclar=kits_mezclar)
        for pk, plk in zip(kp, kplc):
            placements[len(pallets)] = plk
            pallets.append(pk)
        piso = list(piso) + kpiso
        res.avisos += kav
        res.sin_medidas += [x for x in ksm if x not in res.sin_medidas]
    if not pallets and not piso:
        res.avisos.append("SDA Stock: sin pallets resultantes.")
        return res

    vehiculos = asignar_vehiculos(len(pallets)) or [Vehiculo(1, *CAMION50, 0, -1)]
    colocados, filas04, geo = ubicar_pallets(pallets, placements, bloques, vehiculos, pal_L, pal_W,
                                             girar=(pack_L, pack_W) != (pal_L, pal_W))
    piso_pl, piso_filas, vehiculos = cargar_piso(piso, bloques, vehiculos, geo, pal_W,
                                                 restricciones_piso())
    res.placed = colocados + piso_pl
    res.filas04 = filas04 + piso_filas
    res.pallets = [{"numero": i + 1, "tipo": p.tipo or ("Mono" if p.k == 1 else "Mix"),
                    "vehiculo": geo.get(i + 1, {}).get("veh", 0),
                    "x": geo.get(i + 1, {}).get("x", 0.0), "y": geo.get(i + 1, {}).get("y", 0.0),
                    "dl": pal_W, "dw": pal_L} for i, p in enumerate(pallets)]

    # Resumen por camión (equivalente a 03_PedidoCubicado)
    for v in vehiculos:
        del_cam = [p for p in res.placed if p.container == v.numero]
        if not del_cam:
            continue
        vol_cam = v.L * v.w * v.h / 1_000_000.0 or 1.0
        res.camiones.append(Camion(numero=v.numero + cam_offset, tipo=v.tipo, L=v.L, w=v.w, h=v.h))
        agg: list[dict] = []
        for p in del_cam:
            b = bloques[p.fila] if 0 <= p.fila < len(bloques) else None
            cod = b.cod if b else p.cod
            ped = b.pedido if b else p.ped
            f = next((a for a in agg if a["cod"] == cod and a["ped"] == ped), None)
            if f is None:
                f = {"cod": cod, "desc": b.desc if b else p.desc, "u": 0, "v": 0.0,
                     "fila": p.fila, "ped": ped}
                agg.append(f)
            f["u"] += p.n * (max(b.cm_por_caja, 1) if b else 1)
            f["v"] += p.volM3
        peds = []
        for a in agg:
            if a["ped"] not in peds:
                peds.append(a["ped"])
        tipo_carga = "Mono-pedido" if len(peds) <= 1 else f"Multi-pedido (n={len(peds)})"
        acum = 0.0
        for a in agg:
            acum += a["v"]
            res.filas03.append(Fila03(
                camion=v.numero + cam_offset, tipo_camion=v.tipo, cap_m3=vb_round(vol_cam, 2),
                sku=a["cod"], descripcion=a["desc"], unidades=a["u"], ocup_linea=a["v"] / vol_cam,
                ocup_acum=acum / vol_cam, libre_m3=vb_round(vol_cam - acum, 2),
                fila_origen=a["fila"], tipo_carga=tipo_carga, pedido=a["ped"],
                pedidos_camion=", ".join(peds)))
    return res
