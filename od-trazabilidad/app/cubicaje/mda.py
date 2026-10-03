"""Port de Cubicaje_MDA (Cubicación.bas): carga a piso, pedido tras pedido.

Entrada equivalente a las hojas del Excel:
  posiciones -> 02_Posiciones (col C override CM, D SKU, E descripción, F carga, I pedido)
  pedidos    -> 01_Entrada A2:A27 (orden del operador)
  medidas    -> Base medidas
  camiones   -> Config

Salida equivalente a 03_PedidoCubicado, más las colocaciones para el visor 3D.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .core import Box, Item, Placement, Restric, cascada
from .datos import Dims, get_dims_for
from .vb import clng, vb_round

NO_ENCONTRADO = "Producto no Encontrado"


@dataclass
class Posicion:
    sku: str
    desc: str
    carga: float
    pedido: str
    fila: int = 0
    cm_override: str = ""


@dataclass
class Camion:
    numero: int
    tipo: str
    L: float
    w: float
    h: float

    @property
    def vol_m3(self) -> float:
        return self.L * self.w * self.h / 1_000_000.0


@dataclass
class Fila03:
    """Una fila de 03_PedidoCubicado."""
    camion: int
    tipo_camion: str
    cap_m3: float
    sku: str
    descripcion: str
    unidades: int
    ocup_linea: float
    ocup_acum: float
    libre_m3: float
    fila_origen: int
    tipo_carga: str
    pedido: str
    pedidos_camion: str
    sucursal: str = ""          # modos predistribuidos
    ocup_camion: float = 0.0    # ocupación total del camión (lo que muestra la hoja 03 predist)


@dataclass
class Resultado:
    modo: str
    camiones: list[Camion] = field(default_factory=list)
    filas03: list[Fila03] = field(default_factory=list)
    placed: list[Placement] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    sin_medidas: list[str] = field(default_factory=list)
    no_encontrados: list[str] = field(default_factory=list)
    sin_ubicar: dict = field(default_factory=dict)
    filas04: list = field(default_factory=list)      # detalle por pallet (modos SDA)
    pallets: list = field(default_factory=list)      # geometría de los pallets para el visor

    @property
    def unidades(self) -> int:
        return sum(f.unidades for f in self.filas03)


def restricciones_mda() -> Restric:
    """Las mismas banderas que fija Cubicaje_MDA."""
    return Restric(usaPeso=True, usaApilable=True, permiteRotar=False, permiteInclinar=False,
                   usaTopes=False, topeUnidades=0, ordenarPorVolumen=True, cargarDesdeFondo=True,
                   respetarOrden=True,        # pedido tras pedido, sin reordenar global
                   completarBloque=False,     # greedy: el voluminoso arranca desde el fondo
                   motorBestFit=True)         # best-fit por columna (replica EasyCargo)


def construir_items(posiciones: list[Posicion], pedidos: list[str], cache: dict[str, Dims],
                    pasa_filtro=None) -> tuple[list[Item], list[str], list[str], list[str]]:
    """Lee 02_Posiciones pedido por pedido y ordena por volumen DESC dentro de cada pedido."""
    items: list[Item] = []
    sin_medidas: list[str] = []
    no_encontrados: list[str] = []
    huerfanos: list[str] = []
    conocidos = set(pedidos)

    for ped in pedidos:
        desde = len(items)
        for p in posiciones:
            if str(p.pedido).strip() != ped:
                continue
            cod = str(p.sku).strip()
            if not cod:
                continue
            if pasa_filtro is not None and not pasa_filtro(cod):
                continue
            if str(p.desc).strip() == NO_ENCONTRADO:
                no_encontrados.append(cod)
                continue
            qty = clng(p.carga) if isinstance(p.carga, (int, float)) else 0
            if qty <= 0:
                continue
            d = get_dims_for(cache, cod)
            if d is None:
                if cod not in sin_medidas:
                    sin_medidas.append(cod)
                continue
            items.append(Item(cod=cod, desc=p.desc, L=d.L, w=d.w, h=d.h, peso=d.peso,
                              apilable=d.apilable, inclinable=d.inclinable, rotable=d.rotable,
                              qty=qty, fila=p.fila, ped=ped))
        # voluminoso al fondo DENTRO del bloque del pedido (burbuja, volumen DESC)
        bloque = items[desde:]
        n = len(bloque)
        for a in range(n - 1):
            for b in range(n - 1 - a):
                v1 = bloque[b].L * bloque[b].w * bloque[b].h
                v2 = bloque[b + 1].L * bloque[b + 1].w * bloque[b + 1].h
                if v1 < v2:
                    bloque[b], bloque[b + 1] = bloque[b + 1], bloque[b]
        items[desde:] = bloque

    for p in posiciones:                       # SKUs cuyo pedido no está en la lista
        cod = str(p.sku).strip()
        if not cod:
            continue
        ped = str(p.pedido).strip()
        if not ped:
            huerfanos.append(f"{cod} (fila {p.fila}, sin pedido)")
        elif ped not in conocidos:
            huerfanos.append(f"{cod} (fila {p.fila}, pedido {ped} fuera de la lista)")
    return items, sin_medidas, no_encontrados, huerfanos


def escribir_03(placed: list[Placement], n_cont: int, cont_box: list[int], boxes: list[Box],
                pedidos: list[str], cam_offset: int = 0) -> tuple[list[Fila03], list[Camion]]:
    """Escritura de 03_PedidoCubicado: agrega por (SKU, pedido) en orden de carga."""
    filas: list[Fila03] = []
    camiones: list[Camion] = []
    for c in range(1, n_cont + 1):
        bi = cont_box[c] if 1 <= c < len(cont_box) else len(boxes) - 1
        if bi < 0 or bi >= len(boxes):
            bi = len(boxes) - 1
        box = boxes[bi]
        vol_cam = box.vol_m3 or 1.0
        del_cam = [p for p in placed if p.container == c]

        ped_set = []
        for p in del_cam:
            if p.ped not in ped_set:
                ped_set.append(p.ped)
        ped_list = ", ".join(x for x in pedidos if x in ped_set)
        if len(ped_set) <= 1:
            tipo_carga = "Mono-pedido"
        else:
            tipo_carga = f"Multi-pedido (n={len(ped_set)})"

        agg: list[dict] = []
        for p in del_cam:
            fila = next((a for a in agg if a["cod"] == p.cod and a["ped"] == p.ped), None)
            if fila is None:
                fila = {"cod": p.cod, "desc": p.desc, "u": 0, "v": 0.0, "fila": p.fila, "ped": p.ped}
                agg.append(fila)
            fila["u"] += p.n
            fila["v"] += p.volM3

        camiones.append(Camion(numero=c + cam_offset, tipo=box.tipo, L=box.L, w=box.w, h=box.h))
        acum = 0.0
        for a in agg:
            acum += a["v"]
            filas.append(Fila03(
                camion=c + cam_offset, tipo_camion=box.tipo, cap_m3=vb_round(box.vol_m3, 2),
                sku=a["cod"], descripcion=a["desc"], unidades=a["u"],
                ocup_linea=a["v"] / vol_cam, ocup_acum=acum / vol_cam,
                libre_m3=vb_round(box.vol_m3 - acum, 2), fila_origen=a["fila"],
                tipo_carga=tipo_carga, pedido=a["ped"], pedidos_camion=ped_list))
    return filas, camiones


def cubicaje_mda(posiciones: list[Posicion], pedidos: list[str], cache: dict[str, Dims],
                 boxes: list[Box], pasa_filtro=None, cam_offset: int = 0) -> Resultado:
    """Cubicaje_MDA completo: items -> cascada de camiones -> filas de 03."""
    res = Resultado(modo="MDA")
    if not boxes:
        res.avisos.append("No hay camiones configurados.")
        return res
    items, sin_med, no_enc, huerfanos = construir_items(posiciones, pedidos, cache, pasa_filtro)
    res.sin_medidas, res.no_encontrados = sin_med, no_enc
    if huerfanos:
        res.avisos.append("SKUs ignorados (pedido fuera de la lista): " + "; ".join(huerfanos))
    if not items:
        res.avisos.append("Sin SKUs cubicables en MDA.")
        return res

    placed: list[Placement] = []
    n_cont, cont_box = cascada(items, boxes, restricciones_mda(), placed)
    res.placed = placed
    res.filas03, res.camiones = escribir_03(placed, n_cont, cont_box, boxes, pedidos, cam_offset)

    # El VBA no avisa de lo que no alcanzó a colocar; aquí se informa sin alterar el cálculo
    restante = {it.cod: it.qty for it in items if it.qty > 0}
    if restante:
        res.sin_ubicar = restante
        res.avisos.append("Unidades que no se pudieron ubicar: " +
                          ", ".join(f"{k}: {v}" for k, v in restante.items()))
    return res
