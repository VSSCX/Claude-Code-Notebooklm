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
    # En Vercel cada consulta es una invocacion de la funcion: se pregunta con menos frecuencia.
    navegador_cada: int = 30 if os.getenv("VERCEL") else int(os.getenv("NAVEGADOR_SEGUNDOS", "2"))
    # --- Lineas del pedido (OrderItems) para el detalle y el asistente ---
    # El dashboard adivina las columnas de descripcion y precio; si la tabla usa otros nombres, se fijan aqui.
    item_col_desc: str = os.getenv("ITEM_COL_DESC", "").strip()
    item_col_precio: str = os.getenv("ITEM_COL_PRECIO", "").strip()     # precio unitario
    item_col_monto: str = os.getenv("ITEM_COL_MONTO", "").strip()       # monto de la linea (si no hay precio unitario)
    item_col_sku: str = os.getenv("ITEM_COL_SKU", "").strip()           # codigo SAP (por defecto Reference_Code)
    item_precio_centavos: str = os.getenv("ITEM_PRECIO_CENTAVOS", "auto").strip().lower()   # auto | 1 | 0 (VTEX suele guardar en centavos)

    # --- Asistente de consultas (chat) ---
    # Sin configurar usa reglas (funciona sin internet ni IA). Con IA_MODO la IA solo traduce la pregunta
    # a un plan; las cifras las calcula siempre el servidor. Valores: ollama | openai | anthropic
    ia_modo: str = os.getenv("IA_MODO", "").strip().lower()
    ia_url: str = os.getenv("IA_URL", "").strip()
    ia_modelo: str = os.getenv("IA_MODELO", "").strip()
    ia_clave: str = os.getenv("IA_CLAVE", "").strip()
    ia_timeout: int = int(os.getenv("IA_TIMEOUT_SEGUNDOS", "25"))

    # Cuanto tiempo un pedido recien llegado se marca como NUEVO en la tabla.
    nuevo_segundos: int = int(os.getenv("NUEVO_SEGUNDOS", "300"))
    # Modo demo: usa datos de ejemplo en vez de SQL (para probar sin conexión)
    # En Vercel (funciones sin servidor) NUNCA se consultan las bases: ahi solo corre el modo DEMO
    # (ver VERCEL.md). Vercel define la variable VERCEL=1 en cada despliegue.
    serverless: bool = bool(os.getenv("VERCEL"))
    demo: bool = bool(os.getenv("VERCEL")) or os.getenv("DEMO", "").strip().lower() in ("1", "true", "si", "sí", "yes")


settings = Settings()
