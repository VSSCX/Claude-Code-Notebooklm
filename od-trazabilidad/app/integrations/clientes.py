"""Reglas por cliente, en tabla editable.

Antes vivían en el código (pallets, calefones de HITES, híbridos SODIMAC/RIPLEY) y en
las hojas del Excel. Ahora se pueden ver y cambiar desde la plataforma, y agregar un
cliente nuevo no requiere tocar código.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analisis import CLIENTES as _CLIENTES_BASE
from ..analisis import PALLETS as _PALLETS_BASE
from ..models import Cliente, ahora


def _semilla() -> list[dict]:
    filas = []
    for nombre, (grupo, codigo) in _CLIENTES_BASE.items():
        pl = _PALLETS_BASE.get(nombre, (120.0, 100.0, 140.0))
        filas.append({"nombre": nombre, "grupo_sop": grupo, "codigo": codigo,
                      "pallet_largo": float(pl[0]), "pallet_ancho": float(pl[1]),
                      "pallet_alto": float(pl[2]),
                      "calefon_aparte": "HITES" in nombre,
                      "hibrido": nombre in ("SODIMAC", "RIPLEY"),
                      "canal": "RETAIL", "region": "RM"})
    return filas


def asegurar_semilla(s: Session) -> int:
    """La primera vez deja cargados los clientes que estaban en el código."""
    if s.scalar(select(Cliente).limit(1)) is not None:
        return 0
    for f in _semilla():
        s.add(Cliente(**f, actualizado=ahora()))
    s.flush()
    return len(_semilla())


def todos(s: Session) -> list[Cliente]:
    asegurar_semilla(s)
    return list(s.scalars(select(Cliente).order_by(Cliente.nombre)).all())


def buscar(s: Session, nombre: str) -> Cliente | None:
    """Coincidencia exacta o, si no, por contención (PARIS FULL -> PARIS)."""
    n = (nombre or "").strip().upper()
    if not n:
        return None
    asegurar_semilla(s)
    c = s.get(Cliente, n)
    if c is not None:
        return c
    for x in todos(s):
        if x.nombre in n or n in x.nombre:
            return x
    return None


def doc(c: Cliente) -> dict:
    return {"nombre": c.nombre, "grupo_sop": c.grupo_sop, "codigo": c.codigo, "canal": c.canal,
            "region": c.region, "pallet": [c.pallet_largo, c.pallet_ancho, c.pallet_alto],
            "caja_master": c.caja_master, "calefon_aparte": c.calefon_aparte,
            "hibrido": c.hibrido, "notas": c.notas}


def guardar(s: Session, datos: dict) -> Cliente:
    nombre = str(datos.get("nombre", "")).strip().upper()
    if not nombre:
        raise ValueError("Falta el nombre del cliente.")
    c = s.get(Cliente, nombre) or Cliente(nombre=nombre)
    pallet = datos.get("pallet") or [c.pallet_largo, c.pallet_ancho, c.pallet_alto]
    if min(float(x or 0) for x in pallet) <= 0:
        raise ValueError("Las medidas del pallet tienen que ser mayores que cero.")
    c.grupo_sop = str(datos.get("grupo_sop", c.grupo_sop or nombre)).strip()
    c.codigo = str(datos.get("codigo", c.codigo or "")).strip()
    c.canal = str(datos.get("canal", c.canal or "RETAIL")).strip().upper()
    c.region = str(datos.get("region", c.region or "RM")).strip()
    c.pallet_largo, c.pallet_ancho, c.pallet_alto = (float(pallet[0]), float(pallet[1]),
                                                     float(pallet[2]))
    c.caja_master = str(datos.get("caja_master", c.caja_master or "")).strip().upper()
    c.calefon_aparte = bool(datos.get("calefon_aparte", c.calefon_aparte))
    c.hibrido = bool(datos.get("hibrido", c.hibrido))
    c.notas = str(datos.get("notas", c.notas or ""))[:200]
    c.actualizado = ahora()
    s.add(c)
    return c
