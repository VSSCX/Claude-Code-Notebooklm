"""Respaldo automático de la base.

La operación completa vive en un archivo. Al iniciar la plataforma se guarda una copia
del día y se conservan las últimas quince, así un archivo corrupto o borrado nunca
significa perder el historial.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import BASE_DIR, settings

log = logging.getLogger("respaldo")
CARPETA = BASE_DIR / "data" / "respaldos"
CONSERVAR = 15


def _ruta_base() -> Path | None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return None                     # en SQL Server el respaldo lo hace el servidor
    archivo = url.split("///")[-1]
    p = Path(archivo)
    return p if p.is_absolute() else (BASE_DIR / archivo)


def copiar(motivo: str = "inicio") -> dict:
    """Copia la base con la fecha del día. Si ya existe la del día, la reemplaza."""
    origen = _ruta_base()
    if origen is None:
        return {"ok": False, "motivo": "La base no es SQLite: el respaldo lo hace el servidor."}
    if not origen.exists():
        return {"ok": False, "motivo": "Todavía no hay base que respaldar."}
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / f"trazabilidad-{datetime.now():%Y-%m-%d}.db"
    try:
        # Copia consistente aunque la plataforma esté escribiendo
        with sqlite3.connect(origen) as src, sqlite3.connect(destino) as dst:
            src.backup(dst)
    except Exception as e:  # noqa: BLE001 - si falla, se intenta la copia simple
        log.warning("Respaldo con sqlite falló (%s); se copia el archivo", e)
        try:
            shutil.copy2(origen, destino)
        except OSError as err:
            return {"ok": False, "motivo": f"No se pudo respaldar: {err}"}
    limpiar()
    return {"ok": True, "archivo": destino.name, "tamano_kb": round(destino.stat().st_size / 1024),
            "motivo": motivo, "copias": len(listar())}


def listar() -> list[dict]:
    if not CARPETA.exists():
        return []
    copias = sorted(CARPETA.glob("trazabilidad-*.db"), reverse=True)
    return [{"archivo": c.name, "fecha": c.name[14:-3],
             "tamano_kb": round(c.stat().st_size / 1024)} for c in copias]


def limpiar(conservar: int = CONSERVAR) -> int:
    """Deja solo las últimas copias; borra las más viejas."""
    copias = sorted(CARPETA.glob("trazabilidad-*.db"), reverse=True)
    borradas = 0
    for c in copias[conservar:]:
        try:
            c.unlink()
            borradas += 1
        except OSError:
            pass
    return borradas
