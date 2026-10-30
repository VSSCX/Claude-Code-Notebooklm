"""Cubicaje, medidas, kits y cubicador libre, repartidos por tema.

Antes era un solo archivo de 1.283 líneas. Cada módulo tiene sus endpoints y este paquete los junta.

- medidas.py        Base de Medidas, ajustes del cubicaje y medidas de los camiones
- kits.py           listado de kits (carga desde Excel)
- predistribuido.py reparto por sucursal de un pedido
- pedido.py         cubicaje de un pedido y cubicaje conjunto
- libre.py          cubicador libre (sin pedido ni SAP)
- carga_masiva.py   plantilla de carga y su importación
- excel.py          descarga del cubicaje en Excel
- _comun.py         piezas compartidas (guardado, faltantes de medidas, visor)

El orden de inclusión importa solo dentro de cada módulo (por ejemplo /predistribuido/plantilla
va antes de /predistribuido/{numero}).
"""
from fastapi import APIRouter

from . import carga_masiva, excel, kits, libre, medidas, pedido, predistribuido
from .libre import _reparto_por_grupos  # noqa: F401  (lo usan las pruebas)
from .pedido import _cubicar  # noqa: F401  (lo usa el análisis para recubicar)

router = APIRouter()
for _modulo in (medidas, kits, predistribuido, pedido, libre, carga_masiva, excel):
    router.include_router(_modulo.router)
