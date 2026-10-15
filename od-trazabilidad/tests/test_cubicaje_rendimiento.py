"""El motor best-fit debe dar EXACTAMENTE lo mismo que la versión lenta original.

`_bf_referencia` es la implementación anterior (máximo de ventana sobre toda la grilla).
La versión actual recorre la grilla por franjas y corta al encontrar la primera posición
válida; estas pruebas comprueban que el resultado es idéntico, posición por posición.
"""
import random

import numpy as np
import pytest
from numpy.lib.stride_tricks import sliding_window_view

from app.cubicaje import core
from app.cubicaje.core import (EPS, Box, Item, Restric, _Estado, _max_ventana, _mejor_colocacion_bf,
                               _soporte_ok, _suma_ventana, cascada)
from app.cubicaje.vb import ceil_neg_int


def _bf_referencia(it, ch, restric, est, x_min_cell):
    """Copia literal de la versión anterior de _mejor_colocacion_bf."""
    CELL = core.CELL
    cx = max(ceil_neg_int(it.L / CELL), 1)
    cy = max(ceil_neg_int(it.w / CELL), 1)
    oH = it.h
    if cx > est.nx or cy > est.ny:
        return None
    rowmax = sliding_window_view(est.hm, cy, axis=1).max(axis=2)
    winmax = sliding_window_view(rowmax, cx, axis=0).max(axis=2)
    gx0 = max(x_min_cell, 0)
    if gx0 > est.nx - cx:
        return None
    sub = winmax[gx0:]
    ok = sub + oH <= ch + EPS
    if not it.apilable:
        ok &= sub <= EPS
    if not ok.any():
        return None
    valido = ok & (sub <= EPS)
    alturas = np.unique(sub[ok & (sub > EPS)])
    if alturas.size:
        cnt = cx * cy
        if alturas.size > 60:
            for gx_rel, gy in np.argwhere(ok):
                gx, gy = gx0 + int(gx_rel), int(gy)
                z = float(winmax[gx, gy])
                if _soporte_ok(it, restric, est, gx, gy, cx, cy, z):
                    return (gx, gy, z, it.L, it.w, oH, cx, cy)
            return None
        for z in alturas:
            apoya = est.hm >= z - EPS
            onn = _suma_ventana(apoya, cx, cy)[gx0:]
            bien = (onn / cnt) >= 0.7
            if restric.usaApilable:
                bien &= _suma_ventana(apoya & ~est.sopTop, cx, cy)[gx0:] == 0
            if restric.usaPeso:
                liviano = apoya & (est.pesoTop < it.peso - 1e-6)
                bien &= _suma_ventana(liviano, cx, cy)[gx0:] == 0
            valido |= ok & (sub == z) & bien
    if not valido.any():
        return None
    idx = int(np.argmax(valido))
    gx_rel, gy = divmod(idx, valido.shape[1])
    gx = gx0 + gx_rel
    return (gx, gy, float(winmax[gx, gy]), it.L, it.w, oH, cx, cy)


@pytest.fixture(autouse=True)
def _celda():
    antes = core.CELL
    yield
    core.CELL = antes


@pytest.mark.parametrize("k", [1, 2, 3, 5, 8, 13, 31, 64])
@pytest.mark.parametrize("eje", [0, 1])
def test_max_ventana_igual_a_sliding_window(k, eje):
    rng = np.random.default_rng(k * 7 + eje)
    a = rng.integers(0, 50, size=(70, 90)).astype(float)
    if a.shape[eje] < k:
        pytest.skip("ventana mayor que la grilla")
    esperado = sliding_window_view(a, k, axis=eje).max(axis=2 if a.ndim == 2 else -1)
    assert np.array_equal(_max_ventana(a, k, eje), esperado)


def _estado_aleatorio(rng, nx, ny, ch):
    est = _Estado(nx, ny)
    for _ in range(rng.randint(0, 25)):
        x, y = rng.randrange(nx), rng.randrange(ny)
        dx, dy = rng.randint(3, 40), rng.randint(3, 40)
        z = rng.choice([30.0, 60.0, 90.0, 120.0, 180.0, 55.5, 91.0])
        est.hm[x:x + dx, y:y + dy] = np.maximum(est.hm[x:x + dx, y:y + dy], min(z, ch))
        est.pesoTop[x:x + dx, y:y + dy] = rng.choice([5.0, 20.0, 60.0])
        est.sopTop[x:x + dx, y:y + dy] = rng.random() < 0.8
    return est


@pytest.mark.parametrize("celda", [1.0, 2.0])
def test_bf_igual_a_la_referencia_en_estados_aleatorios(celda):
    core.usar_celda(celda)
    rng = random.Random(1234)
    n_comparados = 0
    for _ in range(160):
        ch = rng.choice([230.0, 240.0, 200.0])
        nx, ny = rng.choice([(310, 123), (120, 50), (200, 70)])
        est = _estado_aleatorio(rng, nx, ny, ch)
        it = Item(cod="A", L=rng.choice([20, 40, 61.5, 64, 90]), w=rng.choice([20, 35, 52, 66]),
                  h=rng.choice([15, 48, 90, 150]), peso=rng.choice([5.0, 30.0, 70.0]),
                  apilable=rng.random() < 0.75, qty=5)
        restric = Restric(usaPeso=rng.random() < 0.5, usaApilable=rng.random() < 0.7, motorBestFit=True)
        x_min = rng.choice([0, 0, 0, 10, 80])
        esperado = _bf_referencia(it, ch, restric, est, x_min)
        obtenido = _mejor_colocacion_bf(it, ch, restric, est, x_min)
        assert obtenido == esperado, (it, restric, x_min)
        n_comparados += 1
    assert n_comparados == 160


def _cargas_de_prueba(rng, n_skus, qty_max):
    items = []
    for i in range(n_skus):
        items.append(Item(cod=f"S{i}", L=rng.choice([40, 52, 58, 62, 64, 70]), w=rng.choice([40, 50, 60, 66, 72]),
                          h=rng.choice([20, 48, 88, 92, 175]), peso=rng.choice([9, 14, 36, 62, 66]),
                          apilable=rng.random() < 0.85, qty=rng.randint(5, qty_max), fila=i))
    return items


RESTRICCIONES = [
    dict(usaPeso=True, usaApilable=True, motorBestFit=True),
    dict(usaPeso=False, usaApilable=True, motorBestFit=True),
    dict(usaPeso=True, usaApilable=False, motorBestFit=True, completarBloque=True),   # revierte estados
    dict(usaPeso=True, usaApilable=True, motorBestFit=True, topeUnidades=140),
]


@pytest.mark.parametrize("restr", RESTRICCIONES)
@pytest.mark.parametrize("semilla", [99, 7, 2024])
@pytest.mark.parametrize("celda", [1.0, 2.0])
def test_cascada_completa_igual_a_la_referencia(celda, semilla, restr, monkeypatch):
    """Cubicaje de punta a punta: mismas colocaciones, en el mismo orden."""
    core.usar_celda(celda)
    boxes = [Box("Camion 50", 620, 244, 230), Box("Rampla 53", 1540, 245, 230)]
    restric = Restric(**restr)

    def correr():
        items = _cargas_de_prueba(random.Random(semilla), 9, 30)
        placed = []
        cascada(items, boxes, restric, placed)
        return [(p.cod, p.container, round(p.x, 3), round(p.y, 3), round(p.z, 3), p.n) for p in placed]

    nuevo = correr()
    monkeypatch.setattr(core, "_mejor_colocacion_bf", _bf_referencia)
    referencia = correr()
    assert nuevo == referencia and len(nuevo) > 10
