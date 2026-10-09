"""Pruebas del cubicaje portado desde VBA.

Las de aquí verifican la geometría y las reglas con casos calculables a mano.
La verificación final contra el Excel está en test_casos.py, con los casos de control.
"""
import pytest

from app.cubicaje.core import Box, Item, Restric, cascada, pack
from app.cubicaje.datos import cargar_cache_dims, get_dims_for, get_pallet_dims, leer_camiones
from app.cubicaje.mda import Posicion
from app.cubicaje.motor import Entrada, modo_efectivo, segmentar
from app.cubicaje.vb import clng, fmt_num, round1, vb_int, vb_round
from app.cubicaje.visor import construir_json, letra

RAMPLA = Box("Rampla 53", 1540, 245, 230)
CAM50 = Box("Camion 50", 620, 244, 230)
MDA = Restric(usaPeso=True, usaApilable=True, ordenarPorVolumen=True, cargarDesdeFondo=True,
              respetarOrden=True, motorBestFit=True)


def item(cod, L, w, h, qty, peso=10.0, apilable=True, ped="P1", desc=""):
    return Item(cod=cod, desc=desc or cod, L=L, w=w, h=h, peso=peso, apilable=apilable,
                qty=qty, ped=ped)


# ---------------------------------------------------------------- VBA básico
def test_equivalentes_vba():
    assert clng(2.5) == 2 and clng(3.5) == 4 and clng(2.4) == 2       # redondeo bancario
    assert vb_int(-2.5) == -3 and vb_int(2.9) == 2
    assert vb_round(2.345, 2) == 2.34 and vb_round(86.7785, 2) == 86.78
    assert fmt_num(86.7785) == "86.779" and fmt_num(120.0) == "120" and fmt_num(0) == "0"
    assert round1(86.7785, 2) == 86.78 and round1(0.05, 1) == 0.1
    assert letra(0) == "A" and letra(25) == "Z" and letra(26) == "AA"


# ---------------------------------------------------------------- motor
def test_columna_apilada_y_capacidad():
    """Camión 50 (620x244x230) con cajas de 60x60x80: 10 x 4 columnas de 2 unidades."""
    it = item("A", 60, 60, 80, 1000)
    placed = []
    n = pack([it], CAM50, MDA, placed)
    assert n == 10 * 4 * 2          # 620/60 -> 10 columnas, 244/60 -> 4, altura 230 -> 2 por columna
    assert all(p.n == 2 for p in placed)
    assert placed[0].x == 0 and placed[0].y == 0 and placed[0].z == 0
    assert placed[1].y == 60        # avanza primero en Y (gy asc), como el best-fit del VBA


def test_no_apilable_una_por_columna():
    it = item("A", 60, 60, 80, 100, apilable=False)
    placed = []
    n = pack([it], CAM50, MDA, placed)
    assert n == 10 * 4 and all(p.n == 1 for p in placed)


def test_no_pesado_sobre_liviano():
    """El pesado no se apoya sobre el liviano: queda al lado, no encima."""
    liviano = item("LIV", 240, 240, 100, 1, peso=5)
    pesado = item("PES", 240, 240, 100, 1, peso=500)
    placed = []
    pack([liviano, pesado], Box("chico", 500, 244, 230), MDA, placed)
    assert len(placed) == 2
    assert placed[1].z == 0         # no se subió encima del liviano


def test_sin_espacio_no_coloca():
    it = item("GIGANTE", 2000, 300, 300, 1)
    placed = []
    assert pack([it], CAM50, MDA, placed) == 0 and placed == []


def test_cascada_elige_camion_chico_y_grande():
    """Poco volumen -> camión chico; mucho -> rampla (regla del 92% del VBA)."""
    placed = []
    n_cont, cont_box = cascada([item("A", 60, 60, 80, 8)], [CAM50, RAMPLA], MDA, placed)
    assert n_cont == 1 and cont_box[1] == 0                    # camión 50

    placed = []
    n_cont, cont_box = cascada([item("A", 60, 60, 80, 200)], [CAM50, RAMPLA], MDA, placed)
    assert n_cont >= 1 and cont_box[1] == 1                    # rampla
    assert all(p.container >= 1 for p in placed)


def test_reparto_en_varios_camiones():
    """Lo que no cabe pasa al camión siguiente y nada se pierde ni se duplica."""
    it = item("A", 120, 100, 115, 500)
    placed = []
    n_cont, _ = cascada([it], [CAM50, RAMPLA], MDA, placed)
    assert n_cont >= 2
    assert sum(p.n for p in placed) + it.qty == 500
    for c in range(1, n_cont + 1):
        assert any(p.container == c for p in placed)


# ---------------------------------------------------------------- datos
CAB = ["Grupo", "Descripción", "Piezas", "Longitud", "Anchura", "Altura", "Peso total",
       "Apilar", "Inclinar", "Rotar", "Máx Camión", "Máx Pallet"]
FILAS_BM = [
    ["Grupo", "Descripción", "Piezas", "Longitud", "Anchura", "Altura", "Peso total",
     "Apilar", "Inclinar", "Rotar", "Máx Camión", "Máx Pallet"],
    ["900081624", "900081624 MDWMT16W", 1, 60.0, 65.0, 85.0, 38.5, "Y", "N", "N", 90, 4],
    ["C900081624", "CAJA MASTER MDWMT16W", 4, 120.0, 65.0, 85.0, 154.0, "Y", "N", "N", 40, 2],
    ["", None, None, None, None, None, None, None, None, None, None, None],
    ["900276671", "900276671 COCINA FM5SSC", 1, 62.0, 66.0, 90.0, 40.0, "N", "N", "Y", 80, 3],
]


def test_cache_de_medidas():
    cache = cargar_cache_dims(FILAS_BM)
    assert set(cache) == {"900081624", "c900081624", "900276671"}    # la fila de encabezado no entra
    d = get_dims_for(cache, "900081624")
    assert (d.L, d.w, d.h, d.peso) == (60.0, 65.0, 85.0, 38.5)
    assert d.apilable and not d.rotable and d.max_camion == 90
    assert get_dims_for(cache, "0900081624") is d                    # busca por valor numérico
    assert get_dims_for(cache, "C900081624").piezas == 4
    assert get_dims_for(cache, "999") is None
    assert not get_dims_for(cache, "900276671").apilable


def test_camiones_y_pallet():
    boxes = leer_camiones([["Rampla 53", 1540, 245, 230], ["Camion 50", 620, 244, 230],
                           ["", None, None, None]])
    assert [b.tipo for b in boxes] == ["Camion 50", "Rampla 53"]     # volumen ascendente
    assert get_pallet_dims("PARIS", [["PARIS", "Paris", 266566, 120, 100, 150]]) == (120, 100, 150)
    assert get_pallet_dims("OTRO", []) == (120, 100, 140)            # defaults del VBA


# ---------------------------------------------------------------- MDA
def _entrada_mda(**kw):
    base = dict(
        cliente="PARIS", modo="MDA",
        posiciones=[Posicion(sku="900081624", desc="MDWMT16W", carga=30, pedido="4001", fila=5),
                    Posicion(sku="900276671", desc="COCINA FM5SSC", carga=20, pedido="4001", fila=6)],
        pedidos=["4001"], medidas=cargar_cache_dims(FILAS_BM), camiones=[CAM50, RAMPLA])
    base.update(kw)
    return Entrada(**base)


def test_mda_completo():
    r = segmentar(_entrada_mda())
    assert r.modo == "MDA" and r.camiones
    assert r.unidades == 50                                    # todo cubicado
    assert {f.sku for f in r.filas03} == {"900081624", "900276671"}
    f = r.filas03[0]
    assert f.camion == 1 and f.tipo_carga == "Mono-pedido" and f.pedido == "4001"
    assert f.cap_m3 == vb_round(r.camiones[0].vol_m3, 2)
    acum = [x.ocup_acum for x in r.filas03 if x.camion == 1]
    assert acum == sorted(acum) and acum[-1] <= 1.0
    assert abs(sum(x.ocup_linea for x in r.filas03 if x.camion == 1) - acum[-1]) < 1e-9


def test_mda_multi_pedido_y_orden():
    """Dos pedidos: se cargan en el orden de la lista y la fila lo refleja."""
    e = _entrada_mda(
        posiciones=[Posicion("900081624", "MDWMT16W", 10, "4002", 5),
                    Posicion("900276671", "COCINA", 10, "4001", 6)],
        pedidos=["4001", "4002"])
    r = segmentar(e)
    assert r.filas03[0].pedido == "4001"
    assert r.filas03[0].tipo_carga.startswith("Multi-pedido")
    assert r.filas03[0].pedidos_camion == "4001, 4002"


def test_mda_avisos():
    e = _entrada_mda(posiciones=[
        Posicion("111", "Producto no Encontrado", 5, "4001", 5),
        Posicion("222", "SIN MEDIDAS", 5, "4001", 6),
        Posicion("900081624", "MDWMT16W", 5, "9999", 7),          # pedido fuera de la lista
        Posicion("900081624", "MDWMT16W", 5, "4001", 8)])
    r = segmentar(e)
    assert r.no_encontrados == ["111"] and r.sin_medidas == ["222"]
    assert any("fuera de la lista" in a for a in r.avisos)
    assert r.unidades == 5


def test_carga_cero_y_decimales():
    e = _entrada_mda(posiciones=[Posicion("900081624", "MDWMT16W", 0, "4001", 5),
                                 Posicion("900276671", "COCINA", 2.5, "4001", 6)])
    r = segmentar(e)
    assert r.unidades == 2            # CLng(2.5) = 2 (redondeo bancario), y el 0 se ignora


# ---------------------------------------------------------------- modos y validaciones
def test_modo_efectivo_y_no_portados():
    assert modo_efectivo("MDA", True) == "SDA STOCK"
    assert modo_efectivo("MDA PREDISTRIBUIDO", True) == "SDA PREDISTRIBUIDO"
    assert modo_efectivo("MDA", False) == "MDA"
    # los cuatro modos están disponibles; SDA Predistribuido pide su tabla de reparto
    with pytest.raises(ValueError, match="Predistribuido"):
        segmentar(_entrada_mda(modo="SDA PREDISTRIBUIDO", caja_master="CON CAJA MASTER"))
    # H2 = PALLET manda MDA al motor de pallets, que ya está disponible
    assert segmentar(_entrada_mda(piso_pallet="PALLET", caja_master="SIN CAJA MASTER")).modo == "SDA STOCK"
    with pytest.raises(ValueError):
        segmentar(_entrada_mda(modo="OTRO"))
    with pytest.raises(ValueError):
        segmentar(_entrada_mda(cliente=""))
    with pytest.raises(ValueError):
        segmentar(_entrada_mda(modo="SDA STOCK", caja_master=""))


def test_h2_no_reconocido_avisa_y_sigue():
    r = segmentar(_entrada_mda(piso_pallet="PALET"))
    assert any("no se reconoce" in a for a in r.avisos) and r.unidades == 50


def test_hites_separa_calefones():
    """En HITES los calefones van en camiones aparte, después de los demás."""
    e = _entrada_mda(
        cliente="HITES",
        posiciones=[Posicion("900081624", "MDWMT16W", 20, "4001", 5),
                    Posicion("900276671", "CALEFON", 20, "4001", 6)],
        calefones={"900276671"})
    r = segmentar(e)
    cam_por_sku = {f.sku: f.camion for f in r.filas03}
    assert cam_por_sku["900081624"] != cam_por_sku["900276671"]
    assert cam_por_sku["900276671"] > cam_por_sku["900081624"]
    assert len(r.camiones) == len({f.camion for f in r.filas03})
    assert {p.container for p in r.placed} == {f.camion for f in r.filas03}


# ---------------------------------------------------------------- visor
def test_json_del_visor():
    r = segmentar(_entrada_mda())
    js = construir_json(r.placed, r.camiones)
    assert js.startswith('{"titulo":"Order Desk - Cubicaje B2B","esSda":false')
    import json
    d = json.loads(js)
    assert d["pedido"] == "4001" and len(d["camiones"]) == len(r.camiones)
    c = d["camiones"][0]
    assert c["tipo"] == r.camiones[0].tipo and c["volCap"] > 0
    assert len(c["cajas"]) == sum(p.n for p in r.placed if p.container == 1)
    assert sum(i["n"] for i in c["items"]) == len(c["cajas"])
    assert all(set(x) >= {"cod", "x", "y", "z", "dx", "dy", "dz", "color", "letra"} for x in c["cajas"])


# ---------------------------------------------------------------- MDA Predistribuido
from app.cubicaje.mda_predist import FilaPredist, topear_por_sop, _qsort_mdp  # noqa: E402


def test_tope_por_carga_sop():
    """El predistribuido no puede repartir más de lo que autoriza la carga del análisis."""
    pre = [FilaPredist("SUC-A", "111", 30), FilaPredist("SUC-B", "111", 30),
           FilaPredist("SUC-C", "111", 10), FilaPredist("SUC-A", "222", 5)]
    sucs, skus, qtys = topear_por_sop(pre, {"111": 50})
    assert list(zip(sucs, skus, qtys)) == [("SUC-A", "111", 30), ("SUC-B", "111", 20),
                                           ("SUC-A", "222", 5)]      # 111 se corta en 50, C queda fuera


def test_orden_por_sucursal_igual_al_vba():
    su = ["C", "A", "B", "A"]; sk = ["s1", "s2", "s3", "s4"]; qt = [1, 2, 3, 4]
    _qsort_mdp(su, sk, qt, 0, 3)
    assert su == ["A", "A", "B", "C"]
    assert dict(zip(sk, qt)) == {"s1": 1, "s2": 2, "s3": 3, "s4": 4}   # los pares no se mezclan


def test_mda_predistribuido_agrupa_por_sucursal():
    e = _entrada_mda(
        modo="MDA PREDISTRIBUIDO", caja_master="SIN CAJA MASTER",
        posiciones=[Posicion("900081624", "MDWMT16W", 40, "4001", 5),
                    Posicion("900276671", "COCINA FM5SSC", 40, "4001", 6)],
        predistribuido=[FilaPredist("SUC-02", "900081624", 20), FilaPredist("SUC-01", "900276671", 15),
                        FilaPredist("SUC-01", "900081624", 10)])
    r = segmentar(e)
    assert r.modo == "MDA PREDISTRIBUIDO" and r.unidades == 45
    assert {f.sucursal for f in r.filas03} == {"SUC-01", "SUC-02"}
    # dentro de un camión, las sucursales se cargan en orden alfabético
    primeras = [f.sucursal for f in r.filas03 if f.camion == r.filas03[0].camion]
    assert primeras == sorted(primeras)
    assert all(f.ocup_camion > 0 for f in r.filas03)
    assert all(f.tipo_carga.startswith("Sucursal") for f in r.filas03)


def test_mda_predistribuido_sin_tabla_avisa():
    with pytest.raises(ValueError, match="Predistribuido"):
        segmentar(_entrada_mda(modo="MDA PREDISTRIBUIDO", caja_master="SIN CAJA MASTER"))
    # el VBA exige indicar caja master en todos los modos salvo MDA puro
    with pytest.raises(ValueError, match="CAJA MASTER"):
        segmentar(_entrada_mda(modo="MDA PREDISTRIBUIDO"))


def test_predistribuido_ignora_lo_que_excede_el_sop():
    e = _entrada_mda(
        modo="MDA PREDISTRIBUIDO", caja_master="SIN CAJA MASTER",
        posiciones=[Posicion("900081624", "MDWMT16W", 10, "4001", 5)],
        predistribuido=[FilaPredist("SUC-01", "900081624", 8), FilaPredist("SUC-02", "900081624", 8)])
    r = segmentar(e)
    assert r.unidades == 10           # 8 + 2, el resto queda fuera por el tope del SOP


# ---------------------------------------------------------------- SDA Stock (etapa 1)
from app.cubicaje.sda import (armar_pallets, calcular_capacidades, cap_mono,  # noqa: E402
                              construir_bloques, ordenar_por_volumen, remezclar_flojos,
                              restricciones_sda)

FILAS_SDA = FILAS_BM + [
    ["C900276671", "CAJA MASTER COCINA FM5SSC", 2, 124.0, 66.0, 90.0, 80.0, "Y", "N", "N", 40, 2],
    ["955117816", "955117816 EXPRIMIDOR MJP10", 1, 180.0, 53.0, 48.0, 12.0, "Y", "N", "N", 30, 0],
    ["S135000785", "S135000785 ASPIRADORA STK15", 1, 17.8, 57.0, 15.2, 3.0, "Y", "N", "N", 5160, 54],
]
PAL = (120.0, 100.0, 150.0)          # pallet de PARIS


def _cache_sda():
    return cargar_cache_dims(FILAS_SDA)


def test_bloques_con_caja_master():
    """40 unidades con caja master de 2: 20 cajas; 41 dejan además 1 suelta."""
    cache = _cache_sda()
    pos = [Posicion("900276671", "COCINA FM5SSC", 41, "4001", 5)]
    bl, sin_med, sin_caja = construir_bloques(pos, cache, usa_caja_master=True)
    assert [(b.tipo, b.n, b.cm_por_caja) for b in bl] == [("Caja", 20, 2), ("Suelta", 1, 1)]
    assert bl[0].unidades == 40 and bl[1].unidades == 1
    assert sin_med == [] and sin_caja == []


def test_bloques_sin_caja_master_y_override():
    cache = _cache_sda()
    pos = [Posicion("900276671", "COCINA", 10, "4001", 5)]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=False)
    assert [(b.tipo, b.n) for b in bl] == [("Indiv", 10)]
    # la X de la columna C desactiva la caja master para ese producto
    pos = [Posicion("900276671", "COCINA", 10, "4001", 5, cm_override="x")]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=True)
    assert [(b.tipo, b.n) for b in bl] == [("Indiv", 10)]


def test_bloque_sin_caja_master_disponible_avisa():
    cache = _cache_sda()
    pos = [Posicion("900081624", "MDWMT16W", 5, "4001", 5)]      # no tiene C900081624... sí tiene
    bl, _, sin_caja = construir_bloques(pos, cache, usa_caja_master=True)
    assert bl[0].tipo == "Caja"
    pos = [Posicion("900276672", "COCINA FE4SXC", 5, "4001", 5)]
    cache2 = cargar_cache_dims(FILAS_SDA + [["900276672", "900276672 COCINA FE4SXC", 1, 70, 70, 95,
                                             45, "Y", "N", "N", 60, 2]])
    bl, _, sin_caja = construir_bloques(pos, cache2, usa_caja_master=True)
    assert [(b.tipo, b.n) for b in bl] == [("Indiv", 5)] and sin_caja == ["900276672"]


def test_capacidad_por_pallet():
    """Aspiradora de 17,8 x 57 x 15,2 en pallet de 120 x 100 x 150."""
    cache = _cache_sda()
    pos = [Posicion("S135000785", "ASPIRADORA STK15", 500, "4001", 5)]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=False)
    calcular_capacidades(bl, *PAL, restricciones_sda())
    b = bl[0]
    assert b.cap_pallet > 10 and not b.no_cabe
    # el pallet más bajo admite menos: la altura limita el apilado
    assert cap_mono(b, 120, 100, 150, restricciones_sda()) > cap_mono(b, 120, 100, 40, restricciones_sda())


def test_producto_que_no_cabe_en_el_pallet():
    """El exprimidor mide 180 cm y el pallet 120: se marca para ir a piso."""
    cache = _cache_sda()
    pos = [Posicion("955117816", "EXPRIMIDOR MJP10", 30, "4001", 5)]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=False)
    calcular_capacidades(bl, *PAL, restricciones_sda())
    assert bl[0].no_cabe and bl[0].cap_pallet == 1
    pallets, piso = armar_pallets(bl)
    assert pallets == [] and piso == [(0, 30)]


def test_armado_de_pallets_mono_y_cierre_con_dos_bloques():
    cache = _cache_sda()
    pos = [Posicion("900081624", "MDWMT16W", 200, "4001", 5),
           Posicion("900276671", "COCINA FM5SSC", 30, "4001", 6)]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=False)
    calcular_capacidades(bl, *PAL, restricciones_sda())
    ordenar_por_volumen(bl)
    pallets, piso = armar_pallets(bl)
    assert piso == []
    assert all(p.k <= 2 for p in pallets)                 # al armar, máximo 2 bloques por pallet
    assert all(p.frac <= 1.0 + 1e-6 for p in pallets)
    colocado = {}
    for p in pallets:
        for bi, n in p.contenido:
            colocado[bl[bi].cod] = colocado.get(bl[bi].cod, 0) + n
    assert colocado == {"900081624": 200, "900276671": 30}   # nada se pierde


def test_pallets_flojos_se_remezclan():
    """Un pallet con menos del 60% se deshace y su contenido se reparte."""
    cache = _cache_sda()
    pos = [Posicion("S135000785", "ASPIRADORA STK15", 3, "4001", 5),
           Posicion("900276671", "COCINA FM5SSC", 2, "4001", 6)]
    bl, _, _ = construir_bloques(pos, cache, usa_caja_master=False)
    calcular_capacidades(bl, *PAL, restricciones_sda())
    ordenar_por_volumen(bl)
    pallets, _ = armar_pallets(bl)
    assert any(p.frac < 0.6 for p in pallets)
    finales = remezclar_flojos(pallets, bl)
    total = sum(n for p in finales for _, n in p.contenido)
    assert total == 5 and len(finales) <= len(pallets)
    assert all(p.k > 0 for p in finales)


# ---------------------------------------------------------------- SDA Stock completo
from app.cubicaje.sda import asignar_vehiculos  # noqa: E402


def test_asignacion_de_vehiculos():
    """Hasta 12 pallets: camión 50. Más: ramplas de 30 y el resto en el último."""
    assert [(v.tipo, v.pal_desde, v.pal_hasta) for v in asignar_vehiculos(5)] == [("Camion 50", 1, 5)]
    assert [(v.tipo, v.pal_desde, v.pal_hasta) for v in asignar_vehiculos(12)] == [("Camion 50", 1, 12)]
    v = asignar_vehiculos(35)
    assert [(x.tipo, x.pal_desde, x.pal_hasta) for x in v] == [("Rampla", 1, 30), ("Camion 50", 31, 35)]
    v = asignar_vehiculos(65)
    assert [x.tipo for x in v] == ["Rampla", "Rampla", "Camion 50"]
    assert v[-1].pal_hasta == 65 and asignar_vehiculos(0) == []


def _entrada_sda(**kw):
    base = dict(cliente="PARIS", modo="SDA STOCK", caja_master="SIN CAJA MASTER",
                posiciones=[Posicion("S135000785", "ASPIRADORA STK15", 300, "4001", 5)],
                pedidos=["4001"], medidas=_cache_sda(), camiones=[CAM50, RAMPLA],
                pallet=PAL)
    base.update(kw)
    return Entrada(**base)


def test_sda_stock_completo():
    r = segmentar(_entrada_sda())
    assert r.modo == "SDA STOCK" and r.camiones and r.pallets
    # nada se pierde: las unidades de 04 suman lo pedido
    assert sum(f.unidades for f in r.filas04) == 300
    assert sum(f.unidades for f in r.filas03) == 300
    assert all(f.tipo in ("Mono", "Mix") for f in r.filas04)
    # cada pallet queda dentro de un camión y con su posición
    assert all(p["vehiculo"] >= 1 for p in r.pallets)
    assert {p.container for p in r.placed} <= {c.numero for c in r.camiones}
    # las cajas se apoyan sobre la tarima
    assert all(p.z >= 14.5 - 1e-9 for p in r.placed)


def test_sda_stock_con_caja_master():
    """41 unidades con caja master de 2: 20 cajas (40 unidades) + 1 suelta."""
    r = segmentar(_entrada_sda(caja_master="CON CAJA MASTER",
                               posiciones=[Posicion("900276671", "COCINA FM5SSC", 41, "4001", 5)]))
    assert sum(f.unidades for f in r.filas04) == 41
    cajas = [f for f in r.filas04 if f.cajas and f.unidades == f.cajas * 2]
    assert cajas and sum(f.cajas for f in cajas) == 20


def test_sda_stock_producto_a_piso():
    """El exprimidor no cabe en el pallet: va a piso, detrás de los pallets."""
    r = segmentar(_entrada_sda(posiciones=[
        Posicion("S135000785", "ASPIRADORA STK15", 200, "4001", 5),
        Posicion("955117816", "EXPRIMIDOR MJP10", 20, "4001", 6)]))
    piso = [f for f in r.filas04 if f.tipo == "Piso"]
    assert piso and sum(f.unidades for f in piso) == 20
    assert all(f.pallet == 0 for f in piso)
    assert sum(f.unidades for f in r.filas04) == 220
    # en el camión que lleva pallets, el piso arranca después de ellos
    cam = r.pallets[0]["vehiculo"]
    x_pallets = max(p["x"] for p in r.pallets if p["vehiculo"] == cam)
    x_piso = min(p.x for p in r.placed if p.cod == "955117816" and p.container == cam)
    assert x_piso > x_pallets
    # lo que no alcanzó va en otro camión, no encima de los pallets
    assert {p.container for p in r.placed if p.cod == "955117816"} <= {c.numero for c in r.camiones}


def test_sda_stock_solo_piso_sin_pallets():
    r = segmentar(_entrada_sda(posiciones=[Posicion("955117816", "EXPRIMIDOR MJP10", 30, "4001", 5)]))
    assert sum(f.unidades for f in r.filas04) == 30
    assert all(f.tipo == "Piso" for f in r.filas04) and r.pallets == []


def test_sda_stock_varios_camiones():
    r = segmentar(_entrada_sda(posiciones=[Posicion("S135000785", "ASPIRADORA STK15", 5000, "4001", 5)]))
    assert len(r.camiones) >= 2
    assert sum(f.unidades for f in r.filas04) == 5000
    pallets_por_veh = {}
    for p in r.pallets:
        pallets_por_veh[p["vehiculo"]] = pallets_por_veh.get(p["vehiculo"], 0) + 1
    assert all(n <= 30 for n in pallets_por_veh.values())       # ningún camión pasa su capacidad


def test_sda_stock_pallets_mono_y_mix():
    r = segmentar(_entrada_sda(posiciones=[
        Posicion("S135000785", "ASPIRADORA STK15", 120, "4001", 5),
        Posicion("900081624", "MDWMT16W", 4, "4001", 6)]))
    tipos = {f.tipo for f in r.filas04}
    assert tipos <= {"Mono", "Mix", "Piso"}
    assert sum(f.unidades for f in r.filas04) == 124


# ---------------------------------------------------------------- SDA Predistribuido
from app.cubicaje.sda_predist import (armar_pallets_por_sucursal,  # noqa: E402
                                      construir_bloques_predist, es_cliente_hibrido)


def _entrada_sda_pd(**kw):
    base = dict(cliente="PARIS", modo="SDA PREDISTRIBUIDO", caja_master="SIN CAJA MASTER",
                posiciones=[Posicion("S135000785", "ASPIRADORA STK15", 400, "4001", 5)],
                pedidos=["4001"], medidas=_cache_sda(), camiones=[CAM50, RAMPLA], pallet=PAL,
                predistribuido=[FilaPredist("SUC-01", "S135000785", 150),
                                FilaPredist("SUC-02", "S135000785", 150),
                                FilaPredist("SUC-03", "S135000785", 100)])
    base.update(kw)
    return Entrada(**base)


def test_sda_predist_pallets_por_sucursal():
    r = segmentar(_entrada_sda_pd())
    assert r.modo == "SDA PREDISTRIBUIDO"
    assert sum(f.unidades for f in r.filas04) == 400
    # ningún pallet mono-sucursal mezcla sucursales
    por_pallet = {}
    for f in r.filas04:
        if f.pallet:
            por_pallet.setdefault(f.pallet, set()).add(f.sucursal)
    monos = [p["numero"] for p in r.pallets if p["tipo"] == "Mono-Suc"]
    assert all(len(por_pallet.get(n, set())) <= 1 for n in monos)
    assert {p["sucursal"] for p in r.pallets if p["tipo"] == "Mono-Suc"} <= {"SUC-01", "SUC-02", "SUC-03"}


def test_sda_predist_concho_va_al_pool():
    """Una sucursal con 2+ pallets deja su último pallet flojo al pool (nivel 2 o 3)."""
    cache = _cache_sda()
    pos = [Posicion("S135000785", "ASPIRADORA STK15", 1000, "4001", 5)]
    pre = [FilaPredist("SUC-01", "S135000785", 300), FilaPredist("SUC-02", "S135000785", 300)]
    bl, _, _ = construir_bloques_predist(pre, pos, cache, usa_caja_master=False)
    calcular_capacidades(bl, *PAL, restricciones_sda())
    pallets, pool, piso = armar_pallets_por_sucursal(bl, hibrido=False)
    assert sum(n for p in pallets for _, n in p.contenido) == 600
    assert any(p.tipo in ("Mono-SKU", "Mix") for p in pallets)      # los conchos se reagruparon


def test_cliente_hibrido_manda_conchos_a_piso():
    assert es_cliente_hibrido("SODIMAC") and es_cliente_hibrido("Ripley S.A.")
    assert not es_cliente_hibrido("PARIS")
    r = segmentar(_entrada_sda_pd(cliente="SODIMAC"))
    assert any("híbrido" in a for a in r.avisos)
    assert sum(f.unidades for f in r.filas04) == 400
    assert all(p["tipo"] != "Mix" for p in r.pallets)               # sin pallets mix


def test_sda_predist_topea_por_carga_del_analisis():
    r = segmentar(_entrada_sda_pd(
        posiciones=[Posicion("S135000785", "ASPIRADORA STK15", 200, "4001", 5)]))
    assert sum(f.unidades for f in r.filas04) == 200                # el reparto pedía 400


def test_sda_predist_sku_fuera_del_pedido_avisa():
    r = segmentar(_entrada_sda_pd(
        predistribuido=[FilaPredist("SUC-01", "S135000785", 50), FilaPredist("SUC-01", "999", 10)]))
    assert any("no están en el pedido" in a for a in r.avisos)
    assert sum(f.unidades for f in r.filas04) == 50


def test_sda_predist_con_caja_master_y_bulto_del_cliente():
    """La columna de unidades por bulto del cliente manda sobre la caja master."""
    r = segmentar(_entrada_sda_pd(
        caja_master="CON CAJA MASTER",
        posiciones=[Posicion("900276671", "COCINA FM5SSC", 40, "4001", 5)],
        predistribuido=[FilaPredist("SUC-01", "900276671", 21, por_bulto=2)]))
    assert sum(f.unidades for f in r.filas04) == 21                 # 10 cajas de 2 + 1 suelta


def test_sda_predist_producto_a_piso():
    r = segmentar(_entrada_sda_pd(
        posiciones=[Posicion("955117816", "EXPRIMIDOR MJP10", 40, "4001", 5)],
        predistribuido=[FilaPredist("SUC-01", "955117816", 20), FilaPredist("SUC-02", "955117816", 20)]))
    assert all(f.tipo == "Piso" for f in r.filas04)
    assert sum(f.unidades for f in r.filas04) == 40
    assert {f.sucursal for f in r.filas04} <= {"SUC-01", "SUC-02"}


# ------------------------------------------- capacidad exacta (calibrada con EasyCargo)
def test_capacidad_exacta_sin_grilla():
    """La capacidad se calcula con los centímetros reales, no con celdas de 2 cm."""
    from app.cubicaje.sda import Bloque, cap_mono

    def b(L, w, h, apila=True):
        return Bloque(cod="X", desc="", tipo="Indiv", cm_por_caja=1, n=1, L=L, w=w, h=h,
                      apilable=apila, rotable=False, peso=1, pedido="")

    # El motor llama cap_mono(bloque, pal_L, pal_W, pal_H) y el largo de la caja va sobre pal_W.
    # Con la orientación de EasyCargo, pal_W es el lado de 120 cm del pallet.
    P = (100, 120, 140)          # pallet 120 x 100 x 140 acomodado como EasyCargo
    assert cap_mono(b(29, 64.5, 39), *P) == 12          # campana: 4 x 1 x 3, igual que EasyCargo
    assert cap_mono(b(65.5, 65, 99.5), *P) == 1         # lavadora: solo una
    # producto de 32,5 cm: con grilla de 2 cm entraban 2 filas, con medidas reales entran 3
    assert cap_mono(b(39.4, 32.5, 10.5), *P) == 3 * 3 * 13
    # refrigerador más alto que el pallet y no apilable: va igual, en un nivel
    assert cap_mono(b(71, 96.8, 184.5, apila=False), *P) == 1
    assert cap_mono(b(180, 53, 48), *P) == 0            # no cabe en la huella: se va a piso
    assert cap_mono(b(60, 60, 200), *P) == 2 * 1 * 1    # apilable pero muy alto: un solo nivel
    # con el pallet acomodado como el Excel, la campana entra solo 9 veces
    assert cap_mono(b(29, 64.5, 39), 120, 100, 140) == 9


def test_capacidad_desde_la_tabla():
    """Con capacidad = tabla se usa la columna Máx Pallet de la Base de Medidas."""
    from app.cubicaje.datos import cargar_cache_dims
    from app.cubicaje.sda import calcular_capacidades, construir_bloques, restricciones_sda
    filas = [CAB, ["800001", "800001 PRODUCTO", 1, 30, 30, 30, 5, "Y", "N", "N", 500, 7]]
    cache = cargar_cache_dims(filas)
    bl, _, _ = construir_bloques([Posicion("800001", "800001 PRODUCTO", 20, "4001", 5)],
                                 cache, usa_caja_master=False)
    calcular_capacidades(bl, 120, 100, 140, restricciones_sda(), cache, usar_tabla=True)
    assert bl[0].cap_pallet == 7                      # lo que dice la tabla
    calcular_capacidades(bl, 120, 100, 140, restricciones_sda(), cache, usar_tabla=False)
    assert bl[0].cap_pallet == 4 * 3 * 4              # el cálculo geométrico


# ------------------------------------------- carga exacta de un solo producto por camión
def test_camion_de_un_solo_producto_es_exacto():
    """Un camión con un único SKU se calcula sin grilla: columnas × filas × niveles."""
    from app.cubicaje.core import capacidad_mono, pack

    caja = Box("Rampla 53", 1540, 245, 230)
    it = item("A", 30, 16, 69, 5000, apilable=True)
    placed = []
    n = pack([it], caja, MDA, placed)
    col, fil, niv = capacidad_mono(30, 16, 69, caja, True)
    assert (col, fil, niv) == (51, 15, 3)
    assert n == col * fil * niv == 2295
    # las cajas quedan dentro del camión y sin superponerse
    assert all(p.x + p.oL <= caja.L + 1e-6 and p.y + p.oW <= caja.w + 1e-6 for p in placed)
    assert all(p.z + p.n * p.oH <= caja.h + 1e-6 for p in placed)
    assert len({(p.x, p.y) for p in placed}) == len(placed)


def test_un_solo_producto_no_apilable_y_tope():
    from app.cubicaje.core import pack
    caja = Box("Camion 50", 620, 244, 230)
    it = item("A", 60, 60, 80, 500, apilable=False)
    placed = []
    assert pack([it], caja, MDA, placed) == 10 * 4          # una sola altura
    assert all(p.n == 1 for p in placed)

    restric = Restric(usaPeso=True, usaApilable=True, ordenarPorVolumen=True, cargarDesdeFondo=True,
                      respetarOrden=True, motorBestFit=True, usaTopes=True, topeUnidades=7)
    it2 = item("A", 60, 60, 80, 500)
    placed = []
    assert pack([it2], caja, restric, placed) == 7          # respeta el tope


def test_carga_mixta_sigue_usando_el_motor():
    """Con más de un producto se usa el motor geométrico, no el cálculo exacto."""
    from app.cubicaje.core import pack
    caja = Box("Camion 50", 620, 244, 230)
    its = [item("A", 60, 60, 80, 20), item("B", 40, 50, 30, 20)]
    placed = []
    n = pack(its, caja, MDA, placed)
    assert n == 40 and {p.cod for p in placed} == {"A", "B"}


def test_producto_mas_largo_que_el_camion():
    from app.cubicaje.core import pack
    placed = []
    assert pack([item("A", 700, 100, 100, 5)], Box("Camion 50", 620, 244, 230), MDA, placed) == 0
