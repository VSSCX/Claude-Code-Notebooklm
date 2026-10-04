"""Configuración del dashboard D2C. Lee variables de entorno o el archivo .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    # Servidor Azure de VTEX (Orders / OrderItems). Mismo del .pbix.
    vtex_server: str = os.getenv("VTEX_SERVER", "elxa3sql-customerdata-001.database.windows.net")
    vtex_db: str = os.getenv("VTEX_DB", "Alfred-Cloud")
    # Servidor ODS de SAP (ingresos y facturación). Mismo del .pbix.
    sap_server: str = os.getenv("SAP_SERVER", "clws0156")
    sap_db: str = os.getenv("SAP_DB", "161221_ts_ods")

    # Fecha desde la que los datos están validados (parámetro FechaValidada del .pbix)
    fecha_validada: str = os.getenv("FECHA_VALIDADA", "2026-07-14")

    # Driver ODBC para SQL Server
    odbc_driver: str = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

    # Credenciales de Azure (VTEX / Alfred). Azure NO acepta cuenta de Windows:
    # estos dos son obligatorios.
    vtex_user: str = os.getenv("VTEX_USER", "")
    vtex_pass: str = os.getenv("VTEX_PASS", "")
    # Credenciales del ODS (SAP / clws0156). Si se dejan vacías, usa la cuenta de Windows.
    sap_user: str = os.getenv("SAP_USER", "")
    sap_pass: str = os.getenv("SAP_PASS", "")

    # --- Actualizacion en vivo ---
    # Cada cuantos segundos el servidor hace una consulta LIVIANA (solo conteos) para
    # detectar pedidos nuevos o cambios. Si algo cambio, recarga todo al tiro.
    revisar_cada: int = int(os.getenv("REVISAR_CADA_SEGUNDOS", "10"))
    # Recarga completa de respaldo aunque no se detecte ningun cambio.
    recarga_maxima: int = int(os.getenv("RECARGA_MAXIMA_SEGUNDOS", "300"))
    # Cada cuantos segundos el navegador pregunta al servidor si hay datos nuevos (consulta barata).
    navegador_cada: int = int(os.getenv("NAVEGADOR_SEGUNDOS", "2"))
    # Cuanto tiempo un pedido recien llegado se marca como NUEVO en la tabla.
    nuevo_segundos: int = int(os.getenv("NUEVO_SEGUNDOS", "300"))
    # Modo demo: usa datos de ejemplo en vez de SQL (para probar sin conexión)
    demo: bool = os.getenv("DEMO", "").strip().lower() in ("1", "true", "si", "sí", "yes")


settings = Settings()
