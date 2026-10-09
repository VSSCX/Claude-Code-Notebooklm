"""API de la plataforma, repartida por temas.

Antes esto era un solo archivo de 1.163 líneas con 47 endpoints: cada cambio obligaba
a buscar entre pedidos, SAP, cubicaje y configuración mezclados. Ahora cada tema tiene
su archivo y este solo los junta bajo /api.

- core.py     pedidos, entregas, grupos y bandeja
- sap.py      leer, analizar, crear y borrar en SAP
- cubicaje/   (paquete) cubicaje del pedido, cubicador libre, Base de Medidas y kits
- datos.py    clientes, sesión, respaldos y estado del sistema
"""
from fastapi import APIRouter

from . import admin, core, cubicaje, cuenta, datos, sap

router = APIRouter(prefix="/api")
router.include_router(cuenta.router)
router.include_router(admin.router)
router.include_router(datos.router)
router.include_router(core.router)
router.include_router(sap.router)
router.include_router(cubicaje.router)
