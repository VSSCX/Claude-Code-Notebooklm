"""Lectura de los datos que alimentan el cubicaje, con la misma semántica del VBA.

- CargarCacheDims / GetDimsForC  (hoja "Base medidas", columnas A..L desde la fila 4)
- LeerCamionesB2B                (hoja "Config", ordenados por volumen ascendente)
- GetPalletDims                  (hoja "Clientes", columnas D/E/F)
"""
from __future__ import annotations

from dataclasses import dataclass

from .core import Box
from .vb import cdbl, clng, val

# Columnas de Base medidas (1-based, como el VBA)
COL_BM_GRP, COL_BM_DESC, COL_BM_PCS = 1, 2, 3
COL_BM_L, COL_BM_W, COL_BM_H, COL_BM_PESO = 4, 5, 6, 7
COL_BM_API, COL_BM_INC, COL_BM_ROT = 8, 9, 10
COL_BM_MAX_CAM, COL_BM_MAX_PAL = 11, 12

PAL_DEF_L, PAL_DEF_W, PAL_DEF_H = 120.0, 100.0, 140.0


@dataclass
class Dims:
    L: float
    w: float
    h: float
    apilable: bool
    inclinable: bool
    rotable: bool
    piezas: int
    desc: str
    max_camion: int
    max_pallet: int
    peso: float


def _celda(fila, col: int):
    return fila[col - 1] if len(fila) >= col else None


def cargar_cache_dims(filas) -> dict[str, Dims]:
    """CargarCacheDims: clave = SKU en minúsculas; primera aparición gana.

    Se replica la rareza del VBA: cuando una conversión falla (On Error Resume Next),
    la variable conserva el valor de la fila anterior.
    """
    cache: dict[str, Dims] = {}
    cL = cW = ch = 0.0
    cPcs = 0
    sA = si = sR = sd = ""
    cMaxCam = cMaxPal = 0
    cPeso = 0.0
    for fila in filas:
        grp = str(_celda(fila, COL_BM_GRP) or "").strip()
        if not grp:
            continue
        for col, nombre in ((COL_BM_L, "cL"), (COL_BM_W, "cW"), (COL_BM_H, "ch")):
            v = cdbl(_celda(fila, col))
            if v is not None:
                if nombre == "cL":
                    cL = v
                elif nombre == "cW":
                    cW = v
                else:
                    ch = v
        v = cdbl(_celda(fila, COL_BM_PCS))
        if v is not None:
            cPcs = clng(v)
        sA = str(_celda(fila, COL_BM_API) or "").strip().upper()
        si = str(_celda(fila, COL_BM_INC) or "").strip().upper()
        sR = str(_celda(fila, COL_BM_ROT) or "").strip().upper()
        sd = str(_celda(fila, COL_BM_DESC) or "").strip()
        v = cdbl(_celda(fila, COL_BM_MAX_CAM))
        if v is not None:
            cMaxCam = clng(v)
        v = cdbl(_celda(fila, COL_BM_MAX_PAL))
        if v is not None:
            cMaxPal = clng(v)
        v = cdbl(_celda(fila, COL_BM_PESO))
        if v is not None:
            cPeso = v
        pcs = cPcs if cPcs > 0 else 1
        if cL > 0 and cW > 0 and ch > 0:
            clave = grp.lower()
            if clave not in cache:
                cache[clave] = Dims(L=cL, w=cW, h=ch, apilable=(sA == "Y"), inclinable=(si == "Y"),
                                    rotable=(sR == "Y"), piezas=pcs, desc=sd, max_camion=cMaxCam,
                                    max_pallet=cMaxPal, peso=cPeso)
    return cache


def get_dims_for(cache: dict[str, Dims], sku: str) -> Dims | None:
    """GetDimsForC: busca por clave exacta en minúsculas; si no está, por valor numérico."""
    clave = str(sku or "").strip().lower()
    d = cache.get(clave)
    if d is not None:
        return d
    vsk = val(sku)
    if vsk > 0:
        for k, v in cache.items():       # orden de inserción, como Dictionary.Keys
            if val(k) == vsk:
                return v
    return None


def leer_camiones(filas) -> list[Box]:
    """LeerCamionesB2B: filas (tipo, largo, ancho, alto) ordenadas por volumen ascendente."""
    boxes: list[Box] = []
    for fila in filas:
        tipo = str(_celda(fila, 1) or "").strip()
        if not tipo:
            continue
        L = cdbl(_celda(fila, 2))
        if L is None or _celda(fila, 2) in (None, ""):
            continue
        boxes.append(Box(tipo=tipo, L=L, w=cdbl(_celda(fila, 3)) or 0.0,
                         h=cdbl(_celda(fila, 4)) or 0.0))
    n = len(boxes)
    for i in range(n - 1):                              # burbuja del VBA, volumen ascendente
        for j in range(n - 1 - i):
            if boxes[j].L * boxes[j].w * boxes[j].h > boxes[j + 1].L * boxes[j + 1].w * boxes[j + 1].h:
                boxes[j], boxes[j + 1] = boxes[j + 1], boxes[j]
    return boxes


def get_pallet_dims(cliente: str, filas_clientes) -> tuple[float, float, float]:
    """GetPalletDims: pallet del cliente (columnas D/E/F); si no está, 120x100x140."""
    pL, pW, pH = PAL_DEF_L, PAL_DEF_W, PAL_DEF_H
    objetivo = str(cliente or "").strip().lower()
    for fila in filas_clientes:
        if str(_celda(fila, 1) or "").strip().lower() == objetivo:
            for col, actual in ((4, "L"), (5, "W"), (6, "H")):
                v = cdbl(_celda(fila, col))
                if v and v > 0:
                    if actual == "L":
                        pL = v
                    elif actual == "W":
                        pW = v
                    else:
                        pH = v
            break
    return pL, pW, pH
