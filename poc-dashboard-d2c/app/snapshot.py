"""Snapshot de datos: una copia cifrada, firmada y versionada de lo que lee el tablero (tablas ya filtradas y sin datos personales).

Por que existe: Vercel no alcanza las bases (estan en una red privada) y no debe guardar sus claves. Un agente DENTRO de la red
(publicar_snapshot.py) consulta las bases con credenciales de solo lectura, valida la calidad, empaqueta, cifra y sube; el tablero
publicado solo lee ese paquete. Las bases nunca quedan expuestas y en Vercel no hay credenciales de base de datos.

Formato: Fernet(gzip(JSON{manifiesto, tablas})). Fernet = AES-128-CBC + HMAC-SHA256: confidencial y a prueba de manipulacion
(si alguien cambia un byte, no se abre). El manifiesto trae el linaje: version, fecha, periodo, origen logico, hash de cada tabla,
filas, columnas incluidas y excluidas, version del codigo, quien lo genero y el informe de calidad.
"""
from __future__ import annotations

import getpass
import gzip
import hashlib
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from .config import settings

TABLAS = ("orders", "items", "sap", "fact", "stock", "items_todos", "maestra")
# Columnas de OrderItems que SI viajan (resto, por ejemplo adjuntos o texto libre del cliente, se excluye: minimizacion de datos)
ITEMS_PERMITIDAS = {"sequence", "quantitysku", "referencecode", "skuname", "skuvalue", "skusellingprice", "idsku", "categoryidssku", "slatype",
                    "warehouse", "shippingestimatedate", "listfreightprice", "freightprice", "productname", "name", "description",
                    "sellingprice", "unitprice", "price", "totalprice", "quantity"}
ORIGEN = {"orders": "VTEX · Orders + OrderItems (resumen por pedido)", "items": "VTEX · OrderItems (3 columnas)", "sap": "ODS SAP · od_pedidos_ingresados",
          "fact": "ODS SAP · dp_facturacion", "stock": "ODS SAP · tabla de stock VTEX", "items_todos": "VTEX · OrderItems (columnas permitidas)",
          "maestra": "ODS SAP · maestra de productos"}
LINAJE = ["Fuente (VTEX Azure / ODS SAP)", "Extracción solo lectura", "Controles de calidad", "Minimización de columnas", "Cifrado y firma",
          "Almacén (Vercel Blob / carpeta)", "Tablero (modelo.construir)", "Reportes y asistente"]
_LOCK = threading.Lock()
_CACHE: dict = {"t": 0.0, "datos": None, "puntero": None, "tp": 0.0}


class ErrorSnapshot(RuntimeError):
    pass


def _fernet():
    try:
        from cryptography.fernet import Fernet, MultiFernet
    except ImportError as e:
        raise ErrorSnapshot("Falta instalar 'cryptography' (pip install cryptography).") from e
    claves = [k.strip() for k in settings.snapshot_keys.split(",") if k.strip()]
    if not claves:
        raise ErrorSnapshot("Falta SNAPSHOT_KEYS (genera una con: python seguridad_admin.py claves).")
    try:
        return MultiFernet([Fernet(k.encode()) for k in claves])
    except Exception as e:  # noqa: BLE001
        raise ErrorSnapshot("SNAPSHOT_KEYS no es una clave Fernet válida.") from e


def _norm(c) -> str:
    return "".join(ch for ch in str(c).lower() if ch.isalnum())


def minimizar(nombre: str, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Solo viajan las columnas necesarias. -> (tabla, columnas excluidas)."""
    if nombre != "items_todos" or df is None or df.empty:
        return df, []
    keep = [c for c in df.columns if _norm(c) in ITEMS_PERMITIDAS]
    return df[keep].copy(), [str(c) for c in df.columns if c not in keep]


def _serializar(df: pd.DataFrame) -> tuple[str, dict]:
    dt = {str(c): ("datetime" if pd.api.types.is_datetime64_any_dtype(t) else str(t)) for c, t in df.dtypes.items()}
    return df.to_json(orient="split", date_format="iso", date_unit="ms", force_ascii=False), dt


def _restaurar(texto: str, dt: dict) -> pd.DataFrame:
    df = pd.read_json(io.StringIO(texto), orient="split", dtype=False, convert_dates=False)
    for c, t in dt.items():
        if c not in df:
            continue
        if t == "datetime":
            df[c] = pd.to_datetime(df[c], errors="coerce")
        elif t.startswith(("int", "float")):
            df[c] = pd.to_numeric(df[c], errors="coerce")
            if t.startswith("int") and df[c].notna().all():
                df[c] = df[c].astype(t)
        elif t == "object":
            df[c] = df[c].where(df[c].notna(), None)
    return df


def empaquetar(frames: dict[str, pd.DataFrame], hoy: pd.Timestamp, calidad: dict | None = None, excepcion: str | None = None,
               codigo: str = "") -> tuple[bytes, dict]:
    """-> (paquete cifrado, manifiesto)."""
    tablas, man_t, excl = {}, {}, {}
    for nombre in TABLAS:
        df = frames.get(nombre)
        if df is None:
            df = pd.DataFrame()
        df, fuera = minimizar(nombre, df)
        texto, dt = _serializar(df)
        tablas[nombre] = {"dtypes": dt, "datos": texto}
        man_t[nombre] = {"origen": ORIGEN[nombre], "filas": int(len(df)), "columnas": [str(c) for c in df.columns],
                         "excluidas": fuera, "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest()}
        if fuera:
            excl[nombre] = fuera
    huella = hashlib.sha256("".join(man_t[n]["sha256"] for n in TABLAS).encode()).hexdigest()
    ahora = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    fmin = pd.to_datetime(frames["orders"]["Creation_Date"]).min() if len(frames.get("orders", [])) else None
    fmax = pd.to_datetime(frames["orders"]["Creation_Date"]).max() if len(frames.get("orders", [])) else None
    try:
        quien = getpass.getuser()
    except Exception:  # noqa: BLE001
        quien = "desconocido"
    man = {"id": f"{ahora}-{huella[:8]}", "creado_utc": ahora, "hoy": pd.Timestamp(hoy).isoformat(), "periodo": [None if fmin is None else str(fmin.date()),
           None if fmax is None else str(fmax.date())], "fecha_validada": settings.fecha_validada, "responsable": quien, "codigo": codigo,
           "huella": huella, "tablas": man_t, "linaje": LINAJE, "calidad": calidad, "excepcion": excepcion,
           "uso_de_ia": "Los datos no se usan para entrenar modelos. La IA opcional solo traduce preguntas a planes."}
    crudo = json.dumps({"manifiesto": man, "tablas": tablas}, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(gzip.compress(crudo, 6)), man


def abrir(paquete: bytes) -> tuple[dict[str, pd.DataFrame], dict]:
    """Descifra, verifica la huella de cada tabla y devuelve (tablas, manifiesto). Si algo no calza, falla (integridad)."""
    try:
        crudo = gzip.decompress(_fernet().decrypt(paquete))
    except ErrorSnapshot:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorSnapshot("El paquete de datos no se pudo abrir: clave incorrecta o contenido alterado.") from e
    j = json.loads(crudo)
    man, out = j["manifiesto"], {}
    for nombre, t in j["tablas"].items():
        if hashlib.sha256(t["datos"].encode("utf-8")).hexdigest() != man["tablas"][nombre]["sha256"]:
            raise ErrorSnapshot(f"La tabla {nombre} no coincide con su huella: datos alterados.")
        out[nombre] = _restaurar(t["datos"], t["dtypes"])
    return out, man


# ------------------------------------------------------------------ almacenes
class Local:
    """Carpeta (disco local o compartida en red)."""
    def __init__(self, ruta: str):
        self.dir = Path(ruta)

    def put(self, nombre: str, datos: bytes) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / (nombre + ".tmp")
        tmp.write_bytes(datos)
        tmp.replace(self.dir / nombre)                      # reemplazo atomico: nadie lee un archivo a medio escribir

    def get(self, nombre: str) -> bytes | None:
        f = self.dir / nombre
        return f.read_bytes() if f.exists() else None

    def limpiar(self, conservar: int = 10) -> None:
        for f in sorted(self.dir.glob(f"{settings.snapshot_prefijo}-*.enc"))[:-conservar]:
            f.unlink(missing_ok=True)


class Blob:
    """Vercel Blob por su API REST. Los datos ya van cifrados: aunque la URL del blob fuera publica, no se puede leer sin SNAPSHOT_KEYS."""
    BASE = "https://blob.vercel-storage.com"

    def __init__(self, token: str):
        self.h = {"Authorization": f"Bearer {token}", "x-api-version": "7"}

    def put(self, nombre: str, datos: bytes) -> None:
        req = urllib.request.Request(f"{self.BASE}/{nombre}", data=datos, method="PUT", headers={
            **self.h, "x-add-random-suffix": "0", "x-allow-overwrite": "1", "x-cache-control-max-age": "30",
            "x-content-type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310  (host fijo)
            r.read()

    def get(self, nombre: str) -> bytes | None:
        req = urllib.request.Request(f"{self.BASE}/?prefix={nombre}&limit=5", headers=self.h)
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            blobs = [b for b in json.loads(r.read()).get("blobs", []) if b.get("pathname") == nombre]
        if not blobs:
            return None
        with urllib.request.urlopen(blobs[0]["url"], timeout=120) as r:  # noqa: S310
            return r.read()

    def limpiar(self, conservar: int = 10) -> None:
        return None


def almacen():
    if settings.snapshot_dir:
        return Local(settings.snapshot_dir)
    if settings.blob_token:
        return Blob(settings.blob_token)
    raise ErrorSnapshot("Falta el almacén: define SNAPSHOT_DIR o BLOB_READ_WRITE_TOKEN.")


def _nombre(id_: str) -> str:
    return f"{settings.snapshot_prefijo}-{id_}.enc"


def _puntero_nombre() -> str:
    return f"{settings.snapshot_prefijo}-ultimo.enc"


def publicar(paquete: bytes, man: dict, alm=None) -> None:
    """Sube primero el paquete y DESPUES el puntero: quien lee nunca ve un puntero a un paquete inexistente."""
    alm = alm or almacen()
    alm.put(_nombre(man["id"]), paquete)
    f = _fernet()
    alm.put(_puntero_nombre(), f.encrypt(json.dumps({"id": man["id"], "huella": man["huella"], "creado": man["creado_utc"],
                                                      "sha256": hashlib.sha256(paquete).hexdigest()}).encode()))
    alm.limpiar()


def puntero(alm=None) -> dict | None:
    """Que version es la ultima (barato, con cache corta). None si todavia no hay datos publicados."""
    with _LOCK:
        if _CACHE["puntero"] is not None and time.time() - _CACHE["tp"] < min(settings.snapshot_ttl, 30):
            return _CACHE["puntero"]
    alm = alm or almacen()
    raw = alm.get(_puntero_nombre())
    p = None
    if raw:
        try:
            p = json.loads(_fernet().decrypt(raw))
        except Exception as e:  # noqa: BLE001
            raise ErrorSnapshot("El puntero de datos no se pudo abrir: clave incorrecta o contenido alterado.") from e
    with _LOCK:
        _CACHE.update(puntero=p, tp=time.time())
    return p


def cargar(alm=None) -> tuple[dict[str, pd.DataFrame], dict]:
    """Ultimo paquete publicado (con cache por instancia). Verifica el hash del paquete contra el puntero y cada tabla contra el manifiesto."""
    p = puntero(alm)
    if not p:
        raise ErrorSnapshot("Todavía no hay datos publicados. Ejecuta publicar_snapshot.py en el equipo con acceso a las bases.")
    with _LOCK:
        d = _CACHE["datos"]
        if d is not None and d[1]["id"] == p["id"]:
            return d
    alm = alm or almacen()
    paquete = alm.get(_nombre(p["id"]))
    if paquete is None:
        raise ErrorSnapshot(f"Falta el paquete {p['id']} en el almacén.")
    if hashlib.sha256(paquete).hexdigest() != p["sha256"]:
        raise ErrorSnapshot("El paquete no coincide con el puntero (hash distinto): contenido alterado.")
    r = abrir(paquete)
    with _LOCK:
        _CACHE["datos"] = r
    return r


def manifiesto_publico(man: dict | None) -> dict | None:
    """Linaje para mostrar: sin datos de pedidos, sin nombres de servidores ni de usuarios de base."""
    if not man:
        return None
    return {"id": man["id"], "creado_utc": man["creado_utc"], "periodo": man["periodo"], "responsable": man.get("responsable"),
            "codigo": man.get("codigo"), "huella": man["huella"], "excepcion": man.get("excepcion"), "linaje": man.get("linaje"),
            "tablas": {k: {x: v[x] for x in ("origen", "filas", "columnas", "excluidas", "sha256")} for k, v in man["tablas"].items()},
            "calidad": man.get("calidad"), "uso_de_ia": man.get("uso_de_ia")}


def tabla(nombre: str) -> pd.DataFrame:
    """Una tabla del ultimo paquete publicado (para items y maestra)."""
    return cargar()[0][nombre]


def reiniciar_cache() -> None:
    with _LOCK:
        _CACHE.update(t=0.0, datos=None, puntero=None, tp=0.0)
