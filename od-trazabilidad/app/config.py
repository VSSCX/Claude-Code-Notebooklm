"""Configuración leída desde variables de entorno o el archivo .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _lista(valor: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in valor.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    # SQLite local por defecto. Para SQL Server:
    # mssql+pyodbc://usuario:clave@SERVIDOR/BASE?driver=ODBC+Driver+17+for+SQL+Server
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'trazabilidad.db').as_posix()}"
    )
    # SQL Server de las bases (plan de ventas, saldos). Solo lectura.
    bases_url: str = os.getenv("BASES_URL", "")
    # Usuario de SQL Server (opcional). Sin esto se entra con la cuenta de Windows.
    bases_usuario: str = os.getenv("BASES_USUARIO", "")
    bases_clave: str = os.getenv("BASES_CLAVE", "")
    # Maestra de homologación (descripciones de producto por código SAP)
    maestra_homologacion: str = os.getenv(
        "MAESTRA_HOMOLOGACION",
        r"\\clws0088\userelux\SalesOP\Bases Order Desk\MAESTRA HOMOLOGACION.xlsx")
    # Base de Medidas (descripción y Máx Camión por SKU)
    base_medidas: str = os.getenv(
        "BASE_MEDIDAS",
        r"\\clws0088\userelux\SalesOP\Bases Order Desk\Proyecto de Automatización\Base de Medidas.xlsm")
    # Clave de acceso opcional (vacía = sin clave, como hasta ahora)
    clave_acceso: str = os.getenv("CLAVE_ACCESO", "")

    # Carpeta con la plantilla del visor y sus librerías (three, jspdf, gltf, scania)
    visor_assets: str = os.getenv(
        "VISOR_ASSETS",
        r"\\clws0088\userelux\SalesOP\Bases Order Desk\Proyecto de Automatización\Rutas\Visor")
    # Donde se guardan los visores generados y sus librerías (en un servidor, un volumen persistente)
    visores_dir: str = os.getenv("VISORES_DIR", str(BASE_DIR / "data" / "visores"))
    # Plantilla del visor 3D. Por defecto la de la plataforma (tema claro); se puede
    # apuntar a la del Excel con PLANTILLA_VISOR.
    plantilla_visor: str = os.getenv(
        "PLANTILLA_VISOR", str(BASE_DIR / "web" / "visor" / "Plantilla_Visor.html"))


settings = Settings()
