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
REVISAR_CADA = 60  # segundos

_estado = {"mtime": None, "revisado": 0.0, "datos": {}, "error": ""}
_lock = threading.Lock()


def _sku(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"^0+(?=\d)", "", str(v).strip())


def _leer(ruta: Path) -> dict[str, str]:
    from openpyxl import load_workbook
    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb[HOJA] if HOJA in wb.sheetnames else wb.worksheets[0]
        filas = ws.iter_rows(values_only=True)
        cab = [str(c).strip() if c is not None else "" for c in next(filas)]
        i_cod, i_desc = cab.index(COL_CODIGO), cab.index(COL_DESC)
        datos: dict[str, str] = {}
        for f in filas:
            if len(f) <= max(i_cod, i_desc):
                continue
            sku, desc = _sku(f[i_cod]), str(f[i_desc] or "").strip()
            if sku and desc and sku not in datos:
                datos[sku] = desc
        return datos
    finally:
        wb.close()


def descripciones() -> dict[str, str]:
    ruta = Path(settings.maestra_homologacion) if settings.maestra_homologacion else None
    if ruta is None:
        return {}
    with _lock:
        ahora = time.time()
        if ahora - _estado["revisado"] < REVISAR_CADA and _estado["mtime"] is not None:
            return _estado["datos"]
        _estado["revisado"] = ahora
        try:
            mtime = ruta.stat().st_mtime
            if mtime != _estado["mtime"]:
                _estado["datos"] = _leer(ruta)
                _estado["mtime"] = mtime
                _estado["error"] = ""
        except Exception as e:  # noqa: BLE001 - la plataforma sigue funcionando sin descripciones
            _estado["error"] = str(e)[:200]
            log.warning("No se pudo leer la maestra de homologación: %s", e)
        return _estado["datos"]


def estado() -> dict:
    return {"ruta": settings.maestra_homologacion, "productos": len(_estado["datos"]),
            "error": _estado["error"]}
