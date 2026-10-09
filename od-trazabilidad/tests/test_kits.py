"""Kits: cajas separadas que viajan juntas (motor y carga desde Excel)."""
from collections import defaultdict

from app.cubicaje.datos import Dims
from app.cubicaje.kits import KitDef
from app.cubicaje.mda import Posicion
from app.cubicaje.sda import cubicaje_sda_stock
from app.cubicaje.core import Box


def _d(L, w, h, desc="", peso=20.0):
    return Dims(L=L, w=w, h=h, apilable=True, inclinable=False, rotable=False, piezas=1, desc=desc,
                max_camion=0, max_pallet=0, peso=peso)


CACHE = {"horno": _d(60, 60, 60, "HORNO"), "encim": _d(60, 50, 12, "ENCIMERA"), "campana": _d(90, 50, 30, "CAMPANA"),
         "gigante": _d(130, 110, 60, "GIGANTE")}
KIT = KitDef("KIT1", "Kit cocina", [("horno", 1), ("encim", 1), ("campana", 1)])
KIT2 = KitDef("KIT2", "Kit chico", [("encim", 1), ("campana", 2)])
GIG = KitDef("KITG", "Kit gigante", [("horno", 1), ("gigante", 1)])


def _pos(sku, qty, ped="1"):
    return Posicion(sku=sku, desc=sku, carga=qty, pedido=ped, fila=5)


def _por_pallet(res):
    """pallet -> {componente: unidades}, sin carga a piso."""
    out = defaultdict(lambda: defaultdict(int))
    for f in res.filas04:
        if f.pallet > 0:
            out[f.pallet][f.sku] += f.unidades
    return out


def test_pallet_de_kits_completos_en_cada_pallet():
    res = cubicaje_sda_stock([_pos("KIT1", 30)], CACHE, 120, 100, 150, False, ["1"],
                             kits={"KIT1": KIT})
    pallets = _por_pallet(res)
    assert pallets
    total = defaultdict(int)
    for comp in pallets.values():
        assert set(comp) == {"horno", "encim", "campana"}
        assert len(set(comp.values())) == 1                 # kits completos: igual cantidad de cada componente
        for k, v in comp.items():
            total[k] += v
    assert dict(total) == {"horno": 30, "encim": 30, "campana": 30}
    assert {p["tipo"] for p in res.pallets} == {"Kit"}
    assert not res.sin_medidas and not res.sin_ubicar


def test_el_kit_se_mezcla_con_productos_normales_sin_romperse():
    res = cubicaje_sda_stock([_pos("KIT1", 12), _pos("horno", 10)], CACHE, 120, 100, 150, False, ["1"],
                             kits={"KIT1": KIT})
    unidades = defaultdict(int)
    for f in res.filas04:
        unidades[f.sku] += f.unidades
    assert unidades["horno"] == 22 and unidades["encim"] == 12 and unidades["campana"] == 12
    kit = [p for p in res.pallets if p["tipo"] == "Kit"]
    assert kit and any(p["tipo"] != "Kit" for p in res.pallets)


def test_un_kit_que_no_cabe_en_el_pallet_va_a_piso_con_aviso():
    res = cubicaje_sda_stock([_pos("KITG", 2)], CACHE, 120, 100, 150, False, ["1"], kits={"KITG": GIG})
    assert any("va a piso" in a for a in res.avisos)
    assert not [p for p in res.pallets if p["tipo"] == "Kit"]
    assert sum(f.unidades for f in res.filas04 if f.tipo == "Piso") == 4          # 2 hornos + 2 gigantes


def test_kits_sin_medidas_se_avisan_y_no_se_cubican():
    kit = KitDef("KX", "x", [("horno", 1), ("fantasma", 1)])
    res = cubicaje_sda_stock([_pos("KX", 3), _pos("horno", 1)], CACHE, 120, 100, 150, False, ["1"], kits={"KX": kit})
    assert res.sin_medidas == ["fantasma"] and any("faltan las medidas de fantasma" in a for a in res.avisos)


def test_un_solo_tipo_de_kit_por_pallet_salvo_que_se_active_la_mezcla():
    pos = [_pos("KIT1", 31), _pos("KIT2", 3)]
    kits = {"KIT1": KIT, "KIT2": KIT2}
    res = cubicaje_sda_stock(pos, CACHE, 120, 100, 150, False, ["1"], kits=kits)
    for comp in _por_pallet(res).values():
        assert not ({"horno"} & set(comp) and (comp.get("campana", 0) != comp.get("horno", 0)))   # nunca KIT1 y KIT2 juntos
    assert all(p["tipo"] == "Kit" for p in res.pallets)
    mezc = cubicaje_sda_stock(pos, CACHE, 120, 100, 150, False, ["1"], kits=kits, kits_mezclar=True)
    assert len(mezc.pallets) <= len(res.pallets)
    total = defaultdict(int)
    for f in mezc.filas04:
        total[f.sku] += f.unidades
    assert total["horno"] == 31 and total["encim"] == 34 and total["campana"] == 37       # nada se pierde al mezclar


def test_kits_a_piso_en_mda_viajan_en_camiones_completos():
    from app.cubicaje.mda import cubicaje_mda
    box = [Box(tipo="Rampla", L=1540, w=245, h=235)]
    res = cubicaje_mda([_pos("KIT1", 600)], ["1"], CACHE, box, kits={"KIT1": KIT})
    total = defaultdict(int)
    for f in res.filas03:
        total[f.sku] += f.unidades
    assert dict(total) == {"horno": 600, "encim": 600, "campana": 600}
    assert len(res.camiones) >= 2
    assert not res.sin_ubicar and not any("partido" in a for a in res.avisos)


def test_expandir_kits_en_modos_por_sucursal():
    from app.cubicaje.kits import expandir_a_componentes
    from app.cubicaje.mda_predist import FilaPredist
    pos, pre, usados = expandir_a_componentes([_pos("KIT1", 10)], [FilaPredist("S1", "KIT1", 6), FilaPredist("S2", "KIT1", 9)],
                                              {"KIT1": KIT})
    assert usados == ["KIT1"] and {p.sku: p.carga for p in pos} == {"horno": 10, "encim": 10, "campana": 10}
    assert sum(f.unidades for f in pre if f.sku == "horno") == 10          # no más kits que los del pedido (6 + 4)


# ---------- restricción por cliente: un producto por pallet (SDA Stock) ----------
def _productos_por_pallet(res):
    out = defaultdict(set)
    for f in res.filas04:
        if f.pallet > 0:
            out[f.pallet].add(f.sku)
    return out


def test_sin_la_restriccion_los_excedentes_de_varios_productos_se_mezclan():
    cache = {"a": _d(60, 40, 40, "A"), "b": _d(60, 40, 40, "B"), "c": _d(60, 40, 40, "C")}
    pos = [_pos("a", 30), _pos("b", 30), _pos("c", 30)]
    res = cubicaje_sda_stock(pos, cache, 120, 100, 150, False, ["1"])
    assert any(len(s) > 1 for s in _productos_por_pallet(res).values())


def test_un_producto_por_pallet_no_mezcla_ni_aunque_queden_pocas_unidades():
    cache = {"a": _d(60, 40, 40, "A"), "b": _d(60, 40, 40, "B"), "c": _d(60, 40, 40, "C")}
    pos = [_pos("a", 30), _pos("b", 30), _pos("c", 30)]
    res = cubicaje_sda_stock(pos, cache, 120, 100, 150, False, ["1"], por_producto=True)
    prod = _productos_por_pallet(res)
    assert prod and all(len(s) == 1 for s in prod.values())               # nunca dos productos en un pallet
    assert {p["tipo"] for p in res.pallets} == {"Mono"}
    total = defaultdict(int)
    for f in res.filas04:
        total[f.sku] += f.unidades
    assert dict(total) == {"a": 30, "b": 30, "c": 30}                      # no se pierde nada
    assert any("Un producto por pallet" in a for a in res.avisos)
    # un mismo producto puede ocupar más de un pallet
    grande = cubicaje_sda_stock([_pos("a", 200)], cache, 120, 100, 150, False, ["1"], por_producto=True)
    assert len(grande.pallets) > 1 and all(len(s) == 1 for s in _productos_por_pallet(grande).values())


def test_un_producto_por_pallet_la_caja_master_y_las_sueltas_del_mismo_sku_comparten_pallet():
    cache = {"a": _d(30, 20, 20, "A"), "ca": Dims(L=60, w=40, h=40, apilable=True, inclinable=False, rotable=False,
                                                  piezas=6, desc="CAJA A", max_camion=0, max_pallet=0, peso=10.0)}
    res = cubicaje_sda_stock([_pos("a", 20)], cache, 120, 100, 150, True, ["1"], por_producto=True)    # 3 cajas + 2 sueltas
    prod = _productos_por_pallet(res)
    assert len(prod) == 1 and {p["tipo"] for p in res.pallets} == {"Mono"}
