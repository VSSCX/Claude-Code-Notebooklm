"""Orquestador del cubicaje: modo, forzador PISO/PALLET y segregación de calefones.

Port de SegmentarEnCamiones / ModoEfectivo / EjecutarModo / PasaFiltroCalefon.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .core import Box
from .datos import Dims
from .mda import Posicion, Resultado, cubicaje_mda
from .mda_predist import FilaPredist, cubicaje_mda_predistribuido
from .sda import cubicaje_sda_stock
from .sda_predist import cubicaje_sda_predistribuido

MODOS = ("MDA", "MDA PREDISTRIBUIDO", "SDA STOCK", "SDA PREDISTRIBUIDO")
PORTADOS = MODOS          # los cuatro modos están disponibles


class ModoNoPortado(NotImplementedError):
    pass


@dataclass
class Entrada:
    cliente: str
    modo: str                         # 01_Entrada E2
    posiciones: list[Posicion]
    pedidos: list[str]                # 01_Entrada A2:A27, en orden
    medidas: dict[str, Dims]
    camiones: list[Box]
    caja_master: str = ""             # F2
    piso_pallet: str = ""             # H2: "", PISO o PALLET
    calefones: set = field(default_factory=set)
    predistribuido: list[FilaPredist] = field(default_factory=list)
    pallet: tuple | None = None          # (largo, ancho, alto) del pallet del cliente
    hibrido: bool | None = None          # regla del cliente; None = se deduce del nombre
    orientacion_pallet: str = "largo"    # largo (como EasyCargo) | excel (como el VBA)
    capacidad_pallet: str = "geometria"  # geometria (cálculo exacto) | tabla (Máx Pallet)


def _norm_cod_calefon(cod: str) -> str:
    t = str(cod or "").strip()
    return t[:-2] if len(t) > 2 and t.endswith(".0") else t


def modo_efectivo(modo: str, a_pallet: bool) -> str:
    """ModoEfectivo: H2 = PALLET manda los modos MDA a su equivalente en pallet."""
    if not a_pallet:
        return modo
    return {"MDA": "SDA STOCK", "MDA PREDISTRIBUIDO": "SDA PREDISTRIBUIDO"}.get(modo, modo)


def _ejecutar_modo(modo: str, e: Entrada, pasa_filtro, cam_offset: int) -> Resultado:
    if modo == "MDA":
        return cubicaje_mda(e.posiciones, e.pedidos, e.medidas, e.camiones, pasa_filtro, cam_offset)
    if modo == "SDA STOCK":
        from ..analisis import pallet_cliente
        pal_L, pal_W, pal_H = e.pallet or pallet_cliente(e.cliente)
        return cubicaje_sda_stock(e.posiciones, e.medidas, pal_L, pal_W, pal_H,
                                  str(e.caja_master).upper() == "CON CAJA MASTER", e.pedidos,
                                  pasa_filtro, cam_offset, orientacion=e.orientacion_pallet,
                                  capacidad=e.capacidad_pallet)
    if modo == "SDA PREDISTRIBUIDO":
        from ..analisis import pallet_cliente
        if not e.predistribuido:
            raise ValueError("Falta la tabla Predistribuido (sucursal, SKU y unidades).")
        pal_L, pal_W, pal_H = e.pallet or pallet_cliente(e.cliente)
        return cubicaje_sda_predistribuido(e.posiciones, e.predistribuido, e.medidas, pal_L, pal_W,
                                           pal_H, str(e.caja_master).upper() == "CON CAJA MASTER",
                                           e.cliente, pasa_filtro, cam_offset, hibrido=e.hibrido,
                                           orientacion=e.orientacion_pallet,
                                           capacidad=e.capacidad_pallet)
    if modo == "MDA PREDISTRIBUIDO":
        if not e.predistribuido:
            raise ValueError("Falta la tabla Predistribuido (sucursal, SKU y unidades).")
        return cubicaje_mda_predistribuido(e.posiciones, e.predistribuido, e.medidas, e.camiones,
                                           pasa_filtro, cam_offset)
    raise ModoNoPortado(
        f"El modo '{modo}' todavía no está disponible en la plataforma. "
        f"Modos disponibles: {', '.join(PORTADOS)}. Cubica ese pedido en el Excel.")


def segmentar(e: Entrada) -> Resultado:
    """SegmentarEnCamiones: valida, resuelve el modo y ejecuta (con doble pasada si aplica)."""
    modo = str(e.modo or "").strip().upper()
    if modo not in MODOS:
        raise ValueError(f"Modo no válido: '{e.modo}'. Debe ser uno de: {', '.join(MODOS)}.")
    if not str(e.cliente or "").strip():
        raise ValueError("Falta el cliente.")
    if not e.pedidos:
        raise ValueError("No hay pedidos en la lista.")
    if modo != "MDA" and str(e.caja_master or "").strip().upper() not in ("CON CAJA MASTER", "SIN CAJA MASTER"):
        raise ValueError("Para los modos SDA hay que indicar CON CAJA MASTER o SIN CAJA MASTER.")

    h2 = str(e.piso_pallet or "").strip().upper()
    a_piso, a_pallet = h2 == "PISO", h2.startswith("PALLET")
    avisos = []
    if h2 and not a_piso and not a_pallet:
        avisos.append(f"El valor '{e.piso_pallet}' no se reconoce; se usa el default del modo "
                      f"(vacío, PISO o PALLET).")
    modo = modo_efectivo(modo, a_pallet)

    # HITES: calefones en camión aparte (pasada 1 sin calefones, pasada 2 solo calefones)
    calef = {_norm_cod_calefon(c) for c in (e.calefones or set())}
    es_hites = bool(calef)          # si el cliente trae lista de calefones, se separan
    codigos = {_norm_cod_calefon(p.sku) for p in e.posiciones if str(p.sku).strip()}
    mixto = bool(calef & codigos) and bool(codigos - calef)

    if es_hites and mixto:
        r1 = _ejecutar_modo(modo, e, lambda c: _norm_cod_calefon(c) not in calef, 0)
        r2 = _ejecutar_modo(modo, e, lambda c: _norm_cod_calefon(c) in calef, len(r1.camiones))
        for p in r2.placed:
            p.container += len(r1.camiones)
        res = Resultado(modo=modo,
                        camiones=r1.camiones + r2.camiones,
                        filas03=r1.filas03 + r2.filas03,
                        placed=r1.placed + r2.placed,
                        avisos=r1.avisos + r2.avisos,
                        sin_medidas=r1.sin_medidas + r2.sin_medidas,
                        no_encontrados=r1.no_encontrados + r2.no_encontrados,
                        sin_ubicar={**r1.sin_ubicar, **r2.sin_ubicar})
    else:
        res = _ejecutar_modo(modo, e, None, 0)

    if a_piso:
        avisos.append("H2 = PISO: se fuerza la carga a piso.")
    res.avisos = avisos + res.avisos
    return res
