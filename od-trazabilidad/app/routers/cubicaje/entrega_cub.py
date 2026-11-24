"""El cubicaje de cada entrega.

Al crear una entrega desde el cubicaje de un pedido, el camión que le corresponde se guarda junto a la entrega (cajas, medidas, bultos
y los datos del 3D). Así, aunque el pedido se vuelva a cubicar, se abra otro suministro o se edite la entrega, cualquier entrega
conserva su cubicaje para verlo y bajar el PDF que se carga al portal de operaciones. Las entregas anteriores a este cambio se
reconstruyen la primera vez que se piden, buscando su camión en los cubicajes guardados."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import domain
from ...db import get_session
from ...models import Config, NotaCredito
from ..comun import _clave_cubicaje
from ._comun import _datos_visor, _visor_vivo
from .pedido import _nombre_visor_pedido

router = APIRouter()


def clave_de(entrega: str) -> str:
    return f"cubentrega:{entrega}"


def _solo_camion(visor: str, camion: int, entrega: str = "") -> str:
    """Los datos del 3D con un único camión: el de la entrega (conserva su número para el nombre del PDF)."""
    try:
        d = json.loads(visor)
    except (TypeError, ValueError):
        return ""
    cams = [c for c in d.get("camiones", []) if int(c.get("idx") or 0) == camion]
    if not cams:
        return ""
    d["camiones"] = cams
    if entrega:
        d["entrega"] = entrega                   # el PDF lleva el número de la entrega en el nombre y la cabecera
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def construir(cub: dict, visor: str, camion: int, pedido: str, entrega: str, origen: str = "creada") -> dict | None:
    cam = next((c for c in cub.get("camiones") or [] if c.get("numero") == camion), None)
    if cam is None:
        return None
    return {"entrega": entrega, "pedido": pedido, "camion": camion, "suministro": int(cub.get("suministro") or 1),
            "modo": cub.get("modo", ""), "pallet": cub.get("pallet"), "camion_datos": cam,
            "filas": [f for f in cub.get("filas") or [] if f.get("camion") == camion],
            "carga": next((x for x in cub.get("carga_por_camion") or [] if x.get("camion") == camion), None),
            "visor_json": _solo_camion(visor, camion, entrega), "origen": origen,
            "generado": datetime.now().replace(microsecond=0).isoformat()}


def guardar_de_entrega(s: Session, pedido: str, entrega: str, camion: int, conj: str = "") -> bool:
    """Guarda el camión de una entrega recién creada. Nunca rompe la creación: si algo falla, se reconstruye al pedirlo."""
    try:
        c = s.get(Config, _clave_cubicaje(pedido))
        if c is None:
            return False
        cub = json.loads(c.valor)
        nombre = f"conjunto_{conj}" if conj else _nombre_visor_pedido(pedido, int(cub.get("suministro") or 1))
        doc = construir(cub, _datos_visor(f"{nombre}_datos"), camion, pedido, entrega)
        if doc is None:
            return False
        domain.guardar_config(s, clave_de(entrega), doc)
        return True
    except Exception:  # noqa: BLE001
        return False


def _camion_que_calza(cub: dict, lineas: dict[str, int]) -> int | None:
    por_cam: dict[int, dict[str, int]] = {}
    for f in cub.get("filas") or []:
        d = por_cam.setdefault(f["camion"], {})
        d[f["sku"]] = d.get(f["sku"], 0) + int(f.get("unidades") or 0)
    mejor = None
    for cam, sk in por_cam.items():
        if not all(k in sk for k in lineas):
            continue
        dist = sum(abs(sk.get(k, 0) - lineas.get(k, 0)) for k in set(sk) | set(lineas))
        if mejor is None or dist < mejor[0]:
            mejor = (dist, cam)
    if mejor and mejor[0] <= 0.1 * sum(lineas.values()):
        return mejor[1]
    return None


def reconstruir(s: Session, entrega: str) -> dict | None:
    """Entregas creadas antes de guardar su camión: se busca en los cubicajes guardados del pedido y se deja guardado."""
    e = domain._get_entrega(s, entrega)
    if e is None:
        return None
    pedido = e.pedido_ref.pedido
    lineas: dict[str, int] = {}
    for ln in e.lineas:
        lineas[ln.sku] = lineas.get(ln.sku, 0) + ln.qty
    for n in s.scalars(select(NotaCredito).where(NotaCredito.entrega_id == e.id)):    # lo devuelto con nota de crédito también iba en el camión
        lineas[n.sku] = lineas.get(n.sku, 0) + n.qty
    sm = e.suministro or 1
    fuentes = [f"{_clave_cubicaje(pedido)}:s{sm}", _clave_cubicaje(pedido)] if sm != domain.suministro_actual(s, pedido) \
        else [_clave_cubicaje(pedido), f"{_clave_cubicaje(pedido)}:s{sm}"]
    ref = (e.camion_ref or "").rsplit("-", 1)
    conj, cam_ref = (ref[0], int(ref[1])) if len(ref) == 2 and ref[1].isdigit() else ("", 0)
    for clave in fuentes:
        c = s.get(Config, clave)
        if c is None:
            continue
        cub = json.loads(c.valor)
        camion = cam_ref if cam_ref and any(x.get("numero") == cam_ref for x in cub.get("camiones") or []) else _camion_que_calza(cub, lineas)
        if camion is None:
            continue
        sm_cub = int(cub.get("suministro") or 1)
        nombre = f"conjunto_{conj}" if conj else _nombre_visor_pedido(pedido, sm_cub)
        doc = construir(cub, _datos_visor(f"{nombre}_datos"), camion, pedido, entrega, origen="reconstruida")
        if doc is not None:
            domain.guardar_config(s, clave_de(entrega), doc)
            s.commit()
            return doc
    return None


@router.get("/entregas/{entrega}/cubicaje")
def get_cubicaje_de_entrega(entrega: str, visor: int = 0, s: Session = Depends(get_session)):
    """El camión de una entrega, con su cubicaje. Con `visor=1` trae también los datos del 3D (pesan más)."""
    c = s.get(Config, clave_de(entrega))
    doc = json.loads(c.valor) if c is not None else reconstruir(s, entrega)
    if doc is None:
        raise HTTPException(404, "Esta entrega no salió de un cubicaje de la plataforma, por eso no tiene un camión asociado.")
    doc["tiene_visor"] = bool(doc.get("visor_json"))
    if visor:
        doc["visor_vivo"] = _visor_vivo()
    else:
        doc.pop("visor_json", None)
    return doc
