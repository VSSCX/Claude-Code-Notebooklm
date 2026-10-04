"""Conexión a los dos SQL Server (VTEX en Azure, SAP en el ODS).

Cada servidor usa sus propias credenciales:
- Azure (VTEX/Alfred) exige usuario y clave de SQL (no acepta cuenta de Windows).
- El ODS (clws0156) usa su usuario SQL, o la cuenta de Windows si se deja vacío.

Las consultas son de solo lectura. Si falla la conexión, el resto de la app lo
informa en pantalla sin caerse.
"""
from __future__ import annotations

import warnings

import pandas as pd

from .config import settings

try:
    import pyodbc  # noqa: F401
    _HAY_PYODBC = True
except Exception:
    _HAY_PYODBC = False


class ErrorConexion(RuntimeError):
    pass


def _cadena(server: str, db: str, user: str, pwd: str) -> str:
    partes = [
        f"DRIVER={{{settings.odbc_driver}}}",
        f"SERVER={server}",
        f"DATABASE={db}",
        "TrustServerCertificate=yes",
        "Encrypt=yes",
    ]
    if user:
        partes.append(f"UID={user}")
        partes.append(f"PWD={pwd}")
    else:
        partes.append("Trusted_Connection=yes")
    return ";".join(partes)


def _leer(server: str, db: str, user: str, pwd: str, sql: str, params: tuple = ()) -> pd.DataFrame:
    if not _HAY_PYODBC:
        raise ErrorConexion(
            "No está instalado pyodbc. Instálalo con: pip install pyodbc")
    try:
        cn = pyodbc.connect(_cadena(server, db, user, pwd), timeout=30)
    except Exception as e:  # noqa: BLE001
        raise ErrorConexion(
            f"No se pudo conectar a {server}/{db}. "
            f"Revisa VPN, driver ODBC y credenciales. Detalle: {str(e)[:200]}") from e
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pd.read_sql(sql, cn, params=list(params) if params else None)
    finally:
        cn.close()


def leer_vtex(sql: str, params: tuple = ()) -> pd.DataFrame:
    return _leer(settings.vtex_server, settings.vtex_db,
                 settings.vtex_user, settings.vtex_pass, sql, params)


def leer_sap(sql: str, params: tuple = ()) -> pd.DataFrame:
    return _leer(settings.sap_server, settings.sap_db,
                 settings.sap_user, settings.sap_pass, sql, params)
