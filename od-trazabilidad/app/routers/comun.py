"""Ayudantes compartidos por los routers: claves de configuración y ajustes del motor."""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..integrations import bases, clientes as cli_mod





def _commit(s: Session):
    try:
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(409, "El registro choca con otro existente.") from e


def _clave_analisis(pedido: str) -> str:
    return f"analisis:{pedido}"


def _calefones_de(cliente: str, s: Session = None) -> set:
    """El cliente marcado con "calefones aparte" trae su lista desde SQL Server."""
    regla = cli_mod.buscar(s, cliente) if s is not None else None
    aparte = regla.calefon_aparte if regla is not None else ("HITES" in (cliente or "").upper())
    if not aparte:
        return set()
    try:
        return bases.calefones()
    except Exception:  # noqa: BLE001
        return set()


def _sop_de(cliente: str, s: Session = None) -> tuple[str, str]:
    """(grupo SOP, código de solicitante en SAP) del cliente. Lo editado en Configuración
    (tabla de clientes) manda sobre lo que viene de fábrica en el código."""
    from ..analisis import codigo_cliente, grupo_sop
    grupo, codigo = grupo_sop(cliente), codigo_cliente(cliente)
    regla = cli_mod.buscar(s, cliente) if s is not None else None
    if regla is not None:
        codigo = regla.codigo or codigo
        if (regla.grupo_sop or "").strip().upper() in ("REGION 2", "REGION 3"):
            grupo = regla.grupo_sop.strip().upper()
    return grupo, codigo


AJUSTES_DEFECTO = {"orientacion_pallet": "largo", "celda_cm": 1, "capacidad_pallet": "geometria"}   # 1 cm: más fiel a la carga real (el Excel usa 2 cm)

# Medidas útiles de los vehículos (cm): (nombre, largo, ancho, alto). Se pueden cambiar en Configuración → Medidas de los camiones.
CAMIONES_BASE = {
    "rampla": ("Rampla 53", 1540.0, 245.0, 235.0),
    "camion50": ("Camion 50", 620.0, 244.0, 230.0),
}
LIMITES_CAMION = {"largo": (200.0, 2500.0), "ancho": (100.0, 300.0), "alto": (100.0, 400.0)}      # cm


def medidas_camiones(s: Session) -> dict:
    """{'rampla': {'largo','ancho','alto'}, 'camion50': {...}} en cm: lo guardado en los ajustes, y lo de fábrica donde falte."""
    import json as _json
    from ..models import Config
    c = s.get(Config, "ajustes_cubicaje")
    guardado = (_json.loads(c.valor) if c else {}).get("camiones") or {}
    out = {}
    for clave, (_n, L, W, H) in CAMIONES_BASE.items():
        g = guardado.get(clave) or {}
        out[clave] = {}
        for campo, base in (("largo", L), ("ancho", W), ("alto", H)):
            try:
                v = float(g.get(campo))
            except (TypeError, ValueError):
                v = 0.0
            lo, hi = LIMITES_CAMION[campo]
            out[clave][campo] = v if lo <= v <= hi else base
    return out


def camiones_vista(s: Session) -> dict:
    m = medidas_camiones(s)
    out = {k: (CAMIONES_BASE[k][0], m[k]["largo"], m[k]["ancho"], m[k]["alto"]) for k in m}
    out["pallet"] = ("Pallet", 0.0, 0.0, 0.0)           # se reemplaza por el pallet del cliente
    return out


def camiones_defecto(s: Session) -> list:
    m = medidas_camiones(s)
    return [[CAMIONES_BASE[k][0], m[k]["largo"], m[k]["ancho"], m[k]["alto"]] for k in ("camion50", "rampla")]


def _ajustes_cubicaje(s: Session) -> dict:
    import json as _json
    from ..models import Config
    c = s.get(Config, "ajustes_cubicaje")
    return {**AJUSTES_DEFECTO, **(_json.loads(c.valor) if c else {}), "camiones": medidas_camiones(s)}


def _aplicar_ajustes(s: Session) -> dict:
    """Deja el motor con la precisión elegida antes de cubicar."""
    from ..cubicaje.core import usar_celda
    from ..cubicaje import sda
    a = _ajustes_cubicaje(s)
    usar_celda(float(a.get("celda_cm") or 2))
    m = a["camiones"]
    sda.usar_camiones(("Rampla", m["rampla"]["largo"], m["rampla"]["ancho"], m["rampla"]["alto"]),
                      ("Camion 50", m["camion50"]["largo"], m["camion50"]["ancho"], m["camion50"]["alto"]))
    return a


CAMIONES_VISTA = {
    "rampla": ("Rampla 53", 1540.0, 245.0, 230.0),
    "camion50": ("Camion 50", 620.0, 244.0, 230.0),
    "pallet": ("Pallet", 0.0, 0.0, 0.0),        # se reemplaza por el pallet del cliente
}


CAMIONES_DEFECTO = [["Camion 50", 620, 244, 230], ["Rampla 53", 1540, 245, 230]]


def _clave_cubicaje(pedido: str) -> str:
    return f"cubicaje:{pedido}"
