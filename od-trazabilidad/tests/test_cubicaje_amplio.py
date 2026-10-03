"""Pruebas amplias del cubicaje: muchos productos y medidas, los cuatro modos.

En vez de comparar contra números fijos, se verifican invariantes que tienen que
cumplirse siempre:
  1. No se pierden ni se duplican unidades.
  2. Toda caja queda dentro del camión.
  3. Dos cajas nunca ocupan el mismo espacio.
  4. Lo no apilable no lleva nada encima.
  5. Los pallets caben en el camión y no se pisan entre ellos.
"""
import itertools
import random

import pytest

from app.cubicaje.core import Box
from app.cubicaje.datos import cargar_cache_dims
from app.cubicaje.mda import Posicion
from app.cubicaje.mda_predist import FilaPredist
from app.cubicaje.motor import Entrada, segmentar

CAM50 = Box("Camion 50", 620, 244, 230)
RAMPLA = Box("Rampla 53", 1540, 245, 230)
PALLET = (120.0, 100.0, 150.0)
TOL = 0.51            # tolerancia del motor (celdas de 2 cm y EPS de 0,5)

CAB = ["Grupo", "Descripción", "Piezas", "Longitud", "Anchura", "Altura", "Peso total",
       "Apilar", "Inclinar", "Rotar", "Máx Camión", "Máx Pallet"]

# Catálogo variado: chicos, medianos, grandes, planos, altos, no apilables, pesados,
# uno que no cabe en el pallet y cajas master de distinto tamaño.
CATALOGO = [
    # sku, desc, piezas, L, W, H, peso, apilar, máx camión, máx pallet
    ("100001", "ASPIRADORA CHICA", 1, 17.8, 57.0, 15.2, 3.0, "Y", 5160, 54),
    ("100002", "MICROONDAS", 1, 54.0, 42.0, 32.0, 14.0, "Y", 900, 24),
    ("100003", "LAVADORA", 1, 60.0, 65.0, 85.0, 38.5, "Y", 90, 4),
    ("100004", "REFRIGERADOR ALTO", 1, 70.0, 75.0, 185.0, 80.0, "N", 40, 1),
    ("100005", "COCINA", 1, 62.0, 66.0, 90.0, 40.0, "Y", 80, 3),
    ("100006", "TELEVISOR PLANO", 1, 130.0, 20.0, 80.0, 18.0, "Y", 120, 8),
    ("100007", "HERVIDOR", 1, 22.0, 22.0, 26.0, 1.5, "Y", 9000, 120),
    ("100008", "SECADORA PESADA", 1, 60.0, 60.0, 85.0, 95.0, "Y", 90, 4),
    ("100009", "EXPRIMIDOR LARGO", 1, 180.0, 53.0, 48.0, 12.0, "Y", 30, 0),   # no cabe en pallet
    ("100010", "CAMPANA", 1, 90.0, 50.0, 60.0, 16.0, "Y", 200, 9),
    ("C100001", "CAJA MASTER ASPIRADORA", 6, 60.0, 58.0, 48.0, 19.0, "Y", 400, 12),
    ("C100007", "CAJA MASTER HERVIDOR", 12, 70.0, 45.0, 55.0, 19.0, "Y", 500, 20),
    ("C100002", "CAJA MASTER MICROONDAS", 2, 56.0, 86.0, 34.0, 29.0, "Y", 380, 10),
]
CACHE = cargar_cache_dims([CAB] + [[c[0], f"{c[0]} {c[1]}", c[2], c[3], c[4], c[5], c[6],
                                    c[7], "N", "N", c[8], c[9]] for c in CATALOGO])
SKUS = [c[0] for c in CATALOGO if not c[0].startswith("C")]


# ---------------------------------------------------------------- invariantes
def _cajas(placement):
    """Una colocación es una columna de n cajas apiladas: se expande a cajas sueltas."""
    for u in range(placement.n):
        yield (placement.x, placement.y, placement.z + u * placement.oH,
               placement.oL, placement.oW, placement.oH)


def revisar_geometria(res, camiones_por_tipo):
    fuera, choques = [], []
    por_camion = {}
    for p in res.placed:
        por_camion.setdefault(p.container, []).append(p)
    for cam, placs in por_camion.items():
        info = next((c for c in res.camiones if c.numero == cam), None)
        if info is None:
            fuera.append(f"camión {cam} sin datos")
            continue
        cajas = [c for p in placs for c in _cajas(p)]
        for (x, y, z, dl, dw, dh) in cajas:
            if x < -TOL or y < -TOL or z < -TOL:
                fuera.append(f"camión {cam}: caja en ({x:.1f},{y:.1f},{z:.1f})")
            if x + dl > info.L + TOL or y + dw > info.w + TOL or z + dh > info.h + TOL:
                fuera.append(f"camión {cam}: caja se sale ({x + dl:.1f},{y + dw:.1f},{z + dh:.1f}) "
                             f"vs ({info.L},{info.w},{info.h})")
        for a, b in itertools.combinations(range(len(cajas)), 2):
            ax, ay, az, adl, adw, adh = cajas[a]
            bx, by, bz, bdl, bdw, bdh = cajas[b]
            if (ax < bx + bdl - TOL and bx < ax + adl - TOL and
                    ay < by + bdw - TOL and by < ay + adw - TOL and
                    az < bz + bdh - TOL and bz < az + adh - TOL):
                choques.append(f"camión {cam}: {cajas[a]} choca con {cajas[b]}")
                if len(choques) > 3:
                    return fuera, choques
    return fuera, choques


def revisar_no_apilables(res):
    """Un producto no apilable nunca puede llevar otra caja encima."""
    problemas = []
    no_apilables = {c[0] for c in CATALOGO if c[7] == "N"}
    por_camion = {}
    for p in res.placed:
        por_camion.setdefault(p.container, []).append(p)
    for cam, placs in por_camion.items():
        bases = [p for p in placs if p.cod.lstrip("C") in no_apilables]
        for base in bases:
            if base.n > 1:
                problemas.append(f"camión {cam}: {base.cod} apilado {base.n} veces")
            techo = base.z + base.n * base.oH
            for otro in placs:
                if otro is base:
                    continue
                for (x, y, z, dl, dw, _dh) in _cajas(otro):
                    if (abs(z - techo) <= TOL and x < base.x + base.oL - TOL and
                            base.x < x + dl - TOL and y < base.y + base.oW - TOL and
                            base.y < y + dw - TOL):
                        problemas.append(f"camión {cam}: {otro.cod} sobre {base.cod} (no apilable)")
    return problemas


def unidades_pedidas(res, esperado):
    """Compara lo cubicado con lo pedido (la hoja 03 para MDA, la 04 para SDA)."""
    if res.filas04:
        return sum(f.unidades for f in res.filas04)
    return sum(f.unidades for f in res.filas03)


# ---------------------------------------------------------------- escenarios
def escenario(semilla: int, n_skus: int = 4, max_qty: int = 120):
    r = random.Random(semilla)
    elegidos = r.sample(SKUS, k=min(n_skus, len(SKUS)))
    return [Posicion(sku=s, desc=f"{s} {dict((c[0], c[1]) for c in CATALOGO)[s]}",
                     carga=r.randint(1, max_qty), pedido="4001", fila=i + 5)
            for i, s in enumerate(elegidos)]


def reparto(posiciones, sucursales=("SUC-01", "SUC-02", "SUC-03"), semilla=1):
    r = random.Random(semilla)
    filas = []
    for p in posiciones:
        resto = int(p.carga)
        for suc in sucursales[:-1]:
            if resto <= 1:
                break
            parte = r.randint(1, max(1, resto // 2))
            filas.append(FilaPredist(suc, p.sku, parte))
            resto -= parte
        if resto > 0:
            filas.append(FilaPredist(sucursales[-1], p.sku, resto))
    return filas


def entrada(modo, posiciones, **kw):
    base = dict(cliente="PARIS", modo=modo, posiciones=posiciones, pedidos=["4001"],
                medidas=CACHE, camiones=[CAM50, RAMPLA], pallet=PALLET,
                caja_master="" if modo == "MDA" else "SIN CAJA MASTER")
    base.update(kw)
    return Entrada(**base)


MODOS = ["MDA", "MDA PREDISTRIBUIDO", "SDA STOCK", "SDA PREDISTRIBUIDO"]


@pytest.mark.parametrize("semilla", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("modo", MODOS)
def test_invariantes_por_modo(modo, semilla):
    pos = escenario(semilla)
    extra = {}
    if "PREDISTRIBUIDO" in modo:
        extra["predistribuido"] = reparto(pos, semilla=semilla)
    res = segmentar(entrada(modo, pos, **extra))

    pedido = sum(int(p.carga) for p in pos)
    cubicado = unidades_pedidas(res, pedido)
    sin_medidas = sum(int(p.carga) for p in pos if p.sku in res.sin_medidas)
    assert cubicado + sin_medidas + sum(res.sin_ubicar.values()) == pedido, (
        f"{modo} semilla {semilla}: pedido {pedido}, cubicado {cubicado}, "
        f"sin ubicar {res.sin_ubicar}")

    fuera, choques = revisar_geometria(res, {})
    assert not fuera, f"{modo} semilla {semilla}: {fuera[:3]}"
    assert not choques, f"{modo} semilla {semilla}: {choques[:3]}"
    assert not revisar_no_apilables(res), f"{modo} semilla {semilla}"


@pytest.mark.parametrize("modo", MODOS)
def test_con_caja_master(modo):
    """Los productos con caja master se agrupan y las unidades cuadran."""
    if modo == "MDA":
        pytest.skip("MDA no usa caja master")
    pos = [Posicion("100001", "100001 ASPIRADORA CHICA", 100, "4001", 5),
           Posicion("100007", "100007 HERVIDOR", 50, "4001", 6),
           Posicion("100002", "100002 MICROONDAS", 17, "4001", 7)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, caja_master="CON CAJA MASTER", **extra))
    assert unidades_pedidas(res, 167) == 167
    fuera, choques = revisar_geometria(res, {})
    assert not fuera and not choques


@pytest.mark.parametrize("modo", MODOS)
def test_producto_que_no_cabe_en_pallet(modo):
    pos = [Posicion("100009", "100009 EXPRIMIDOR LARGO", 40, "4001", 5),
           Posicion("100007", "100007 HERVIDOR", 60, "4001", 6)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, **extra))
    assert unidades_pedidas(res, 100) == 100
    if "SDA" in modo:
        piso = [f for f in res.filas04 if f.tipo == "Piso"]
        assert sum(f.unidades for f in piso) == 40      # el exprimidor va a piso
    fuera, choques = revisar_geometria(res, {})
    assert not fuera and not choques


@pytest.mark.parametrize("modo", MODOS)
def test_un_solo_producto_de_una_unidad(modo):
    pos = [Posicion("100003", "100003 LAVADORA", 1, "4001", 5)]
    extra = {"predistribuido": [FilaPredist("SUC-01", "100003", 1)]} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, **extra))
    assert unidades_pedidas(res, 1) == 1 and len(res.camiones) == 1


@pytest.mark.parametrize("modo", MODOS)
def test_pedido_grande_usa_varios_camiones(modo):
    pos = [Posicion("100003", "100003 LAVADORA", 600, "4001", 5),
           Posicion("100004", "100004 REFRIGERADOR ALTO", 200, "4001", 6)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, **extra))
    assert unidades_pedidas(res, 800) == 800
    assert len(res.camiones) >= 3
    fuera, choques = revisar_geometria(res, {})
    assert not fuera and not choques


@pytest.mark.parametrize("modo", MODOS)
def test_producto_no_apilable(modo):
    """El refrigerador no es apilable: nunca debe quedar nada encima."""
    pos = [Posicion("100004", "100004 REFRIGERADOR ALTO", 30, "4001", 5),
           Posicion("100007", "100007 HERVIDOR", 100, "4001", 6)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, **extra))
    assert unidades_pedidas(res, 130) == 130
    assert not revisar_no_apilables(res)


def test_pallets_no_se_pisan_en_el_camion():
    """En SDA, dos pallets del mismo camión no pueden ocupar el mismo espacio."""
    pos = [Posicion("100007", "100007 HERVIDOR", 400, "4001", 5),
           Posicion("100001", "100001 ASPIRADORA CHICA", 300, "4001", 6)]
    res = segmentar(entrada("SDA STOCK", pos))
    por_camion = {}
    for p in res.pallets:
        por_camion.setdefault(p["vehiculo"], []).append(p)
    for cam, pals in por_camion.items():
        for a, b in itertools.combinations(pals, 2):
            solapa = (a["x"] < b["x"] + b["dl"] - TOL and b["x"] < a["x"] + a["dl"] - TOL and
                      a["y"] < b["y"] + b["dw"] - TOL and b["y"] < a["y"] + a["dw"] - TOL)
            assert not solapa, f"camión {cam}: pallets {a['numero']} y {b['numero']} se pisan"


def test_muchos_productos_a_la_vez():
    """Los 10 productos del catálogo juntos, en los cuatro modos."""
    pos = [Posicion(c[0], f"{c[0]} {c[1]}", 40, "4001", i + 5)
           for i, c in enumerate(CATALOGO) if not c[0].startswith("C")]
    for modo in MODOS:
        extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
        res = segmentar(entrada(modo, pos, **extra))
        assert unidades_pedidas(res, 400) == 400, modo
        fuera, choques = revisar_geometria(res, {})
        assert not fuera, (modo, fuera[:2])
        assert not choques, (modo, choques[:2])


def test_carga_cero_y_valores_raros():
    pos = [Posicion("100003", "100003 LAVADORA", 0, "4001", 5),
           Posicion("100007", "100007 HERVIDOR", 2.5, "4001", 6),
           Posicion("100002", "Producto no Encontrado", 10, "4001", 7)]
    res = segmentar(entrada("MDA", pos))
    assert unidades_pedidas(res, 2) == 2 and res.no_encontrados == ["100002"]


# ---------------------------------------------------------------- casos especiales
def test_h2_pallet_y_piso_cambian_el_motor():
    """H2 = PALLET manda los modos MDA al motor de pallets; PISO deja todo a piso."""
    pos = [Posicion("100007", "100007 HERVIDOR", 200, "4001", 5)]
    r_piso = segmentar(entrada("MDA", pos, piso_pallet="PISO"))
    assert r_piso.modo == "MDA" and not r_piso.pallets
    r_pal = segmentar(entrada("MDA", pos, piso_pallet="PALLET", caja_master="SIN CAJA MASTER"))
    assert r_pal.modo == "SDA STOCK" and r_pal.pallets
    assert unidades_pedidas(r_pal, 200) == 200
    pre = reparto(pos)
    r_pd = segmentar(entrada("MDA PREDISTRIBUIDO", pos, piso_pallet="PALLET",
                             caja_master="SIN CAJA MASTER", predistribuido=pre))
    assert r_pd.modo == "SDA PREDISTRIBUIDO" and unidades_pedidas(r_pd, 200) == 200


@pytest.mark.parametrize("modo", MODOS)
def test_hites_separa_calefones_en_todos_los_modos(modo):
    pos = [Posicion("100005", "100005 COCINA", 60, "4001", 5),
           Posicion("100010", "100010 CAMPANA", 40, "4001", 6)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    res = segmentar(entrada(modo, pos, cliente="HITES", calefones={"100010"}, **extra))
    assert unidades_pedidas(res, 100) == 100
    cam_de = {}
    filas = res.filas04 or res.filas03
    for f in filas:
        cam = f.vehiculo if hasattr(f, "vehiculo") else f.camion
        cam_de.setdefault(f.sku, set()).add(cam)
    assert cam_de["100005"].isdisjoint(cam_de["100010"]), "los calefones deben ir aparte"
    fuera, choques = revisar_geometria(res, {})
    assert not fuera and not choques


def test_clientes_hibridos_sin_pallets_mix():
    pos = [Posicion("100007", "100007 HERVIDOR", 300, "4001", 5),
           Posicion("100001", "100001 ASPIRADORA CHICA", 120, "4001", 6)]
    for cliente in ("SODIMAC", "RIPLEY"):
        res = segmentar(entrada("SDA PREDISTRIBUIDO", pos, cliente=cliente,
                                predistribuido=reparto(pos)))
        assert unidades_pedidas(res, 420) == 420
        assert all(p["tipo"] != "Mix" for p in res.pallets), cliente
        assert any("híbrido" in a for a in res.avisos)


def test_varios_pedidos_en_el_mismo_camion():
    pos = [Posicion("100007", "100007 HERVIDOR", 50, "4001", 5),
           Posicion("100001", "100001 ASPIRADORA CHICA", 30, "4002", 6),
           Posicion("100002", "100002 MICROONDAS", 20, "4001", 7)]
    res = segmentar(Entrada(cliente="PARIS", modo="MDA", posiciones=pos, pedidos=["4001", "4002"],
                            medidas=CACHE, camiones=[CAM50, RAMPLA], pallet=PALLET))
    assert unidades_pedidas(res, 100) == 100
    # el primer camión respeta el orden de la lista de pedidos
    primeros = [f.pedido for f in res.filas03 if f.camion == res.filas03[0].camion]
    assert primeros[0] == "4001"
    multi = [f for f in res.filas03 if f.tipo_carga.startswith("Multi")]
    assert not multi or all("4001" in f.pedidos_camion for f in multi)
    fuera, choques = revisar_geometria(res, {})
    assert not fuera and not choques


def test_sin_medidas_no_rompe():
    pos = [Posicion("999999", "999999 DESCONOCIDO", 50, "4001", 5),
           Posicion("100007", "100007 HERVIDOR", 30, "4001", 6)]
    for modo in MODOS:
        extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
        res = segmentar(entrada(modo, pos, **extra))
        assert "999999" in res.sin_medidas, modo
        assert unidades_pedidas(res, 30) == 30, modo


@pytest.mark.parametrize("modo", MODOS)
def test_rendimiento_pedido_grande(modo):
    """Un pedido grande tiene que cubicarse en segundos, no en minutos."""
    import time
    pos = [Posicion("100007", "100007 HERVIDOR", 900, "4001", 5),
           Posicion("100003", "100003 LAVADORA", 200, "4001", 6),
           Posicion("100006", "100006 TELEVISOR PLANO", 150, "4001", 7)]
    extra = {"predistribuido": reparto(pos)} if "PREDISTRIBUIDO" in modo else {}
    t0 = time.time()
    res = segmentar(entrada(modo, pos, **extra))
    tardo = time.time() - t0
    assert unidades_pedidas(res, 1250) == 1250
    assert tardo < 90, f"{modo} tardó {tardo:.0f}s"
