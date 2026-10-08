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

    # --- Servidor con cuentas por analista ---
    # Vacío: si no hay cuentas creadas la plataforma sigue abierta (un PC, una persona). "obligatoria": pide
    # entrar siempre; sin cuentas, la primera se crea desde el propio servidor o con ADMIN_INICIAL.
    autenticacion: str = os.getenv("AUTENTICACION", "").strip().lower()
    # Administrador de partida: usuario:clave:Nombre completo. Se crea solo si todavía no hay cuentas.
    admin_inicial: str = os.getenv("ADMIN_INICIAL", "")
    # Poner en 1 cuando se sirve por HTTPS: la cookie de sesión viaja solo cifrada.
    cookie_segura: bool = os.getenv("COOKIE_SEGURA", "").strip().lower() in ("1", "true", "si", "sí", "yes")
    # Horas de inactividad tras las que se pide entrar de nuevo
    sesion_horas: int = int(os.getenv("SESION_HORAS", "10"))
    # Cuánto se guarda el historial y los errores (días)
    retencion_actividad_dias: int = int(os.getenv("RETENCION_ACTIVIDAD_DIAS", "365"))
    retencion_errores_dias: int = int(os.getenv("RETENCION_ERRORES_DIAS", "120"))
    # Log en archivo (una línea JSON por petición y por error): para quien administra el servidor
    logs_dir: str = os.getenv("LOGS_DIR", str(BASE_DIR / "data" / "logs"))

    # Carpeta donde SAP deja la exportación de ZSD001_03. Debe ser una ruta del PC donde corre SAP GUI,
    # corta y sin tildes. Vacío: data\sap dentro de la instalación (con respaldo automático si no sirve).
    sap_export_dir: str = os.getenv("SAP_EXPORT_DIR", "")

    # Copia opcional de la exportación de ZSD001_03 en otra ruta (p. ej. la carpeta de red que usaba la macro del
    # Excel), con el nombre "Qty En Entrega.xlsx". Vacío (por defecto): no se copia; la plataforma trabaja con su
    # carpeta local data\sap, que es la que siempre llega bien.
    zsd_publicar_dir: str = os.getenv("ZSD_PUBLICAR_DIR", "")

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
