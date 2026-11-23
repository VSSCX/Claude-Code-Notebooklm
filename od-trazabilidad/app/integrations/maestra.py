"""Descripciones de producto desde la MAESTRA HOMOLOGACION (xlsx en la red).

Se lee la hoja "MAESTRA HOMOLOGACION", cruzando "COD. PROD. PROVEEDOR (ELUX)"
(código SAP) con "Descripción". El archivo se vuelve a leer solo cuando cambia,
y como máximo se revisa una vez por minuto, para no golpear la red.
Si el archivo no está disponible, las descripciones quedan vacías sin romper nada.
"""
import logging
import re
import threading
import time
from pathlib import Path

from ..config import settings

log = logging.getLogger(__name__)

HOJA = "MAESTRA HOMOLOGACION"
COL_CODIGO = "COD. PROD. PROVEEDOR (ELUX)"
COL_DESC = "Descripción"
COL_CLIENTE = "NOMBRE CLIENTE"          # con SKU CLIENTE: el código del producto en el cliente → el código Electrolux
COL_SKU_CLIENTE = "SKU CLIENTE"
COL_ACTIVO = "ACTIVO"
SIN_CODIGO = ("", "0", "-")             # marcas de «este cliente no tiene código para el producto»
REVISAR_CADA = 60  # segundos

_estado = {"mtime": None, "revisado": 0.0, "datos": {}, "homolog": {}, "error": ""}
_lock = threading.Lock()


def _sku(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"^0+(?=\d)", "", str(v).strip())


def _leer(ruta: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Descripciones por código Electrolux y, por cliente, el código Electrolux de cada código del cliente."""
    from openpyxl import load_workbook
    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb[HOJA] if HOJA in wb.sheetnames else wb.worksheets[0]
        filas = ws.iter_rows(values_only=True)
        cab = [str(c).strip() if c is not None else "" for c in next(filas)]
        i_cod, i_desc = cab.index(COL_CODIGO), cab.index(COL_DESC)
        i_cli = cab.index(COL_CLIENTE) if COL_CLIENTE in cab else None
        i_sku_cli = cab.index(COL_SKU_CLIENTE) if COL_SKU_CLIENTE in cab else None
        i_act = cab.index(COL_ACTIVO) if COL_ACTIVO in cab else None
        datos: dict[str, str] = {}
        homolog: dict[str, dict[str, str]] = {}
        activos: set[tuple[str, str]] = set()
        for f in filas:
            if len(f) <= max(i_cod, i_desc):
                continue
            sku, desc = _sku(f[i_cod]), str(f[i_desc] or "").strip()
            if sku and desc and sku not in datos:
                datos[sku] = desc
            if sku and i_cli is not None and i_sku_cli is not None and len(f) > max(i_cli, i_sku_cli):
                cli, cod = str(f[i_cli] or "").strip().upper(), _sku(f[i_sku_cli]).lower()
                if not cli or cod in SIN_CODIGO:
                    continue
                activo = i_act is not None and len(f) > i_act and str(f[i_act]).strip() in ("1", "1.0", "True")
                por_cli = homolog.setdefault(cli, {})
                # un código del cliente con dos productos Electrolux: gana el activo, y entre iguales el primero
                if cod not in por_cli or (activo and (cli, cod) not in activos):
                    por_cli[cod] = sku
                    if activo:
                        activos.add((cli, cod))
        return datos, homolog
    finally:
        wb.close()


def descripciones() -> dict[str, str]:
    ruta = Path(settings.maestra_homologacion) if settings.maestra_homologacion else None
    if ruta is None:
        return {}
    # si otra petición ya está leyendo la red, se usa lo último que hay en vez de esperarla
    if not _lock.acquire(blocking=False):
        return _estado["datos"]
    try:
        ahora = time.time()
        if ahora - _estado["revisado"] < REVISAR_CADA:        # también tras un fallo: no se reintenta a cada petición
            return _estado["datos"]
        _estado["revisado"] = ahora
        try:
            mtime = ruta.stat().st_mtime
            if mtime != _estado["mtime"]:
                _estado["datos"], _estado["homolog"] = _leer(ruta)
                _estado["mtime"] = mtime
                _estado["error"] = ""
        except Exception as e:  # noqa: BLE001 - la plataforma sigue funcionando sin descripciones
            _estado["error"] = str(e)[:200]
            log.warning("No se pudo leer la maestra de homologación: %s", e)
        return _estado["datos"]
    finally:
        _lock.release()


def homologacion(cliente: str = "") -> dict[str, str]:
    """Código del cliente (en minúsculas, sin ceros a la izquierda) → código Electrolux, de la maestra de homologación.
    Con el cliente, solo sus códigos (PARIS FULL usa los de PARIS). Sin cliente, o si la maestra no lo conoce, los códigos que no
    se repiten entre clientes con distinto producto."""
    descripciones()                                    # revisa si el archivo cambió
    por_cliente = _estado["homolog"]
    n = (cliente or "").strip().upper()
    if n:
        for nombre, mapa in por_cliente.items():
            if nombre == n or nombre in n or n in nombre:
                return dict(mapa)
    todos: dict[str, str] = {}
    chocan: set[str] = set()
    for mapa in por_cliente.values():
        for cod, sku in mapa.items():
            if cod in todos and todos[cod] != sku:
                chocan.add(cod)
            todos.setdefault(cod, sku)
    return {c: s for c, s in todos.items() if c not in chocan}


def estado() -> dict:
    return {"ruta": settings.maestra_homologacion, "productos": len(_estado["datos"]),
            "error": _estado["error"]}
