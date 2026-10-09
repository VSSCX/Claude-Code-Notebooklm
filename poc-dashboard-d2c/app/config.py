"""Configuración del dashboard D2C. Lee variables de entorno o el archivo .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _txt(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


# Fuente "snapshot": en vez de consultar las bases (que Vercel no alcanza ni debe guardar), el tablero lee una copia cifrada y
# firmada que un agente dentro de la red publica (publicar_snapshot.py). Ver SEGURIDAD.md.
_SNAP_OK = bool(_txt("SNAPSHOT_KEYS")) and bool(_txt("SNAPSHOT_DIR") or _txt("BLOB_READ_WRITE_TOKEN"))


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

    # --- Maestra de productos (clasificacion 2 y producto por codigo SAP), para el grafico de ventas por Clasif2 ---
    # Nombre de la tabla (por ejemplo dbo.maestra_productos) y en que servidor esta: sap (el ODS) o vtex. Las columnas se
    # adivinan por nombre (codigoSap, Clasif2, Descripcion...); si no calzan, se fijan aqui.
    maestra_tabla: str = os.getenv("MAESTRA_TABLA", "").strip()
    maestra_origen: str = os.getenv("MAESTRA_ORIGEN", "sap").strip().lower()
    maestra_col_sku: str = os.getenv("MAESTRA_COL_SKU", "").strip()
    maestra_col_clasif2: str = os.getenv("MAESTRA_COL_CLASIF2", "").strip()
    maestra_col_producto: str = os.getenv("MAESTRA_COL_PRODUCTO", "").strip()

    # --- Stock VTEX: tabla del ODS (por defecto bi_stock_vtex). Si no existe o sus columnas no calzan, se busca sola entre las tablas "stock" ---
    stock_tabla: str = os.getenv("STOCK_TABLA", "").strip()
    stock_origen: str = os.getenv("STOCK_ORIGEN", "sap").strip().lower()
    stock_col_sku: str = os.getenv("STOCK_COL_SKU", "").strip()
    stock_col_vtex: str = os.getenv("STOCK_COL_VTEX", "").strip()
    stock_col_reservado: str = os.getenv("STOCK_COL_RESERVADO", "").strip()
    # El stock se carga APARTE del resto (no frena el tablero): se espera hasta STOCK_ESPERA_SEGUNDOS la primera vez, se reutiliza
    # STOCK_TTL_SEGUNDOS y la consulta se corta a los STOCK_TIMEOUT_SEGUNDOS.
    stock_espera: int = int(os.getenv("STOCK_ESPERA_SEGUNDOS", "20"))
    stock_ttl: int = int(os.getenv("STOCK_TTL_SEGUNDOS", "600"))
    stock_timeout: int = int(os.getenv("STOCK_TIMEOUT_SEGUNDOS", "180"))

    # --- Asistente de consultas (chat) ---
    # Sin configurar usa reglas (funciona sin internet ni IA). Con IA_MODO la IA solo traduce la pregunta
    # a un plan; las cifras las calcula siempre el servidor. Valores: ollama | openai | anthropic
    ia_modo: str = os.getenv("IA_MODO", "").strip().lower()
    ia_url: str = os.getenv("IA_URL", "").strip()
    ia_modelo: str = os.getenv("IA_MODELO", "").strip()
    ia_clave: str = os.getenv("IA_CLAVE", "").strip()
    ia_redactar: bool = os.getenv("IA_REDACTAR", "").strip().lower() in ("1", "true", "si", "sí", "yes")   # la IA explica las cifras ya calculadas
    ia_timeout: int = int(os.getenv("IA_TIMEOUT_SEGUNDOS", "25"))
    # Donde se guarda el historial de preguntas del asistente (vacio = data/historial_asistente.jsonl; en Vercel solo en memoria)
    asistente_historial: str = os.getenv("ASISTENTE_HISTORIAL", "").strip()

    # --- Seguridad (ver SEGURIDAD.md) ---
    # Usuarios: "correo:hash:rol;correo2:hash2:rol2" (rol = lector | analista | admin). Los hashes se crean con seguridad_admin.py.
    dash_usuarios: str = _txt("DASH_USUARIOS")
    session_secret: str = _txt("SESSION_SECRET")                         # firma de las sesiones (obligatorio si hay usuarios en un servidor publico)
    auth_requerida: str = _txt("AUTH_REQUERIDA", "auto").lower()         # auto | 1 | 0
    sesion_horas: int = int(_txt("SESION_HORAS", "8"))
    auditoria_archivo: str = _txt("AUDITORIA_ARCHIVO")                   # vacio = data/auditoria.jsonl (en Vercel solo en los logs)
    alerta_webhook: str = _txt("ALERTA_WEBHOOK")                         # Teams/Slack: avisa si falla la publicacion de datos
    # Snapshot cifrado (AES + firma, Fernet). SNAPSHOT_KEYS admite varias claves separadas por coma: la primera cifra, todas descifran (rotacion).
    snapshot_keys: str = _txt("SNAPSHOT_KEYS")
    snapshot_dir: str = _txt("SNAPSHOT_DIR")                             # carpeta local o compartida (alternativa a Vercel Blob)
    blob_token: str = _txt("BLOB_READ_WRITE_TOKEN")                      # Vercel Blob
    snapshot_prefijo: str = _txt("SNAPSHOT_PREFIJO", "d2c")
    snapshot_ttl: int = int(_txt("SNAPSHOT_TTL_SEGUNDOS", "60"))
    fuente_snapshot: bool = _SNAP_OK and (bool(os.getenv("VERCEL")) or _txt("FUENTE").lower() == "snapshot")

    # Cuanto tiempo un pedido recien llegado se marca como NUEVO en la tabla.
    nuevo_segundos: int = int(os.getenv("NUEVO_SEGUNDOS", "300"))
    # Modo demo: usa datos de ejemplo en vez de SQL (para probar sin conexión)
    # En Vercel (funciones sin servidor) NUNCA se consultan las bases: ahi solo corre el modo DEMO
    # (ver VERCEL.md). Vercel define la variable VERCEL=1 en cada despliegue.
    serverless: bool = bool(os.getenv("VERCEL"))
    demo: bool = (bool(os.getenv("VERCEL")) and not _SNAP_OK) or os.getenv("DEMO", "").strip().lower() in ("1", "true", "si", "sí", "yes")


settings = Settings()
