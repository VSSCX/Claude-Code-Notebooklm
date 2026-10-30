"""Verifica los casos de control capturados desde el Excel.

Hoy solo revisa que estén bien formados. Cuando exista el motor de cubicaje en
Python, aquí se agrega la comparación contra 'esperado', y un caso pasa solo si
reproduce exactamente las hojas 03 y 04 que produce el Excel.
"""
import json
from pathlib import Path

import pytest

CASOS = sorted((Path(__file__).resolve().parent.parent / "casos").glob("*.json"))


@pytest.mark.skipif(not CASOS, reason="todavía no hay casos capturados")
@pytest.mark.parametrize("ruta", CASOS, ids=lambda r: r.stem)
def test_caso_bien_formado(ruta):
    c = json.loads(ruta.read_text(encoding="utf-8"))
    for clave in ("parametros", "posiciones", "medidas", "pallet", "camiones", "esperado"):
        assert clave in c, f"falta {clave}"
    assert c["parametros"]["pedido"], "sin número de pedido"
    assert c["parametros"]["tipo_pedido"] in (
        "MDA", "MDA PREDISTRIBUIDO", "SDA STOCK", "SDA PREDISTRIBUIDO"), "E2 inválido"
    assert c["posiciones"], "sin posiciones"
    assert c["pallet"], "no se encontró el pallet del cliente en la hoja Clientes"

    skus_medidas = {m["Grupo"].lstrip("C") for m in c["medidas"]}
    faltan = {p["sku"] for p in c["posiciones"] if p["qty_entrega"] > 0} - skus_medidas
    assert not faltan, f"SKU sin medidas: {', '.join(sorted(faltan))}"

    esperado = c["esperado"]["03_PedidoCubicado"] + c["esperado"]["04_CubicajeSDA"]
    assert esperado, "el caso no trae resultado esperado"


# ---------------------------------------------------------------------------
# Verificación del port: el motor Python tiene que reproducir las hojas del Excel
# ---------------------------------------------------------------------------
ORDEN_BM = ["Grupo", "Descripción", "Piezas", "Longitud", "Anchura", "Altura", "Peso total",
            "Apilar", "Inclinar", "Rotar", "Máx Camión", "Máx Pallet"]


def _entrada_desde_caso(c):
    from app.cubicaje.datos import cargar_cache_dims, leer_camiones
    from app.cubicaje.mda import Posicion
    from app.cubicaje.motor import Entrada
    par = c["parametros"]
    pedidos, vistos = [], set()
    for p in c["posiciones"]:                      # orden de aparición, como A2:A27
        ped = str(p.get("pedido") or par["pedido"]).strip()
        if ped and ped not in vistos:
            vistos.add(ped)
            pedidos.append(ped)
    return Entrada(
        cliente=par["cliente"], modo=par["tipo_pedido"],
        posiciones=[Posicion(sku=str(p["sku"]), desc=p.get("descripcion", ""),
                             carga=float(p.get("qty_entrega") or 0),
                             pedido=str(p.get("pedido") or par["pedido"]).strip(), fila=i + 5)
                    for i, p in enumerate(c["posiciones"])],
        pedidos=pedidos or [par["pedido"]],
        medidas=cargar_cache_dims([[m.get(k, "") for k in ORDEN_BM] for m in c["medidas"]]),
        camiones=leer_camiones([[m.get("Tipo camion", ""), m.get("Largo (cm)"),
                                 m.get("Ancho (cm)"), m.get("Alto (cm)")] for m in c["camiones"]]),
        caja_master=par.get("caja_master", ""), piso_pallet=par.get("tipo_carga", ""))


def _esperado_03(c):
    out = {}
    for f in c["esperado"]["03_PedidoCubicado"]:
        cam = str(f.get("Camion #", "")).strip()
        sku = str(f.get("Codigo SAP", "")).strip()
        if not cam or not sku:
            continue
        out[(cam, sku)] = out.get((cam, sku), 0) + int(float(f.get("Unidades") or 0))
    return out


@pytest.mark.skipif(not CASOS, reason="todavía no hay casos capturados")
@pytest.mark.parametrize("ruta", CASOS, ids=lambda r: r.stem)
def test_motor_reproduce_el_excel(ruta):
    from app.cubicaje.motor import ModoNoPortado, segmentar
    c = json.loads(ruta.read_text(encoding="utf-8"))
    try:
        r = segmentar(_entrada_desde_caso(c))
    except ModoNoPortado as e:
        pytest.skip(str(e))
    obtenido = {}
    for f in r.filas03:
        obtenido[(str(f.camion), str(f.sku))] = obtenido.get((str(f.camion), str(f.sku)), 0) + f.unidades
    esperado = _esperado_03(c)
    if not esperado:
        pytest.skip("el caso no trae filas de 03_PedidoCubicado")
    difs = [f"camión {cam} · SKU {sku}: Excel {esperado.get((cam, sku), 0)} vs Python {obtenido.get((cam, sku), 0)}"
            for cam, sku in sorted(set(esperado) | set(obtenido))
            if esperado.get((cam, sku), 0) != obtenido.get((cam, sku), 0)]
    assert not difs, "Diferencias contra el Excel:\n  " + "\n  ".join(difs)
