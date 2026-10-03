"""Acciones que la plataforma puede ejecutar en el libro de Excel (solo Windows).

Cada acción llama a un envoltorio del módulo TrazWebAcciones.bas, que devuelve
una cadena de estado ("OK...", "ERROR ..."). Nada se ejecuta si no está en el
catálogo y habilitado en .env.

El servidor debe correr con TU usuario de Windows (no como servicio), porque
SAP GUI scripting necesita la sesión interactiva.
"""
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..config import BASE_DIR, settings

DIR_ARCHIVOS = BASE_DIR / "data" / "archivos"

PEDIDO = {"nombre": "pedido", "patron": r"^\d{4,12}$", "etiqueta": "N° de pedido"}
ENTREGA = {"nombre": "entrega", "patron": r"^\d{4,12}$", "etiqueta": "N° de entrega"}

CATALOGO = [
    {"id": "actualizar_bases", "macro": "TrazWeb_ActualizarBases", "label": "Actualizar bases",
     "ayuda": "Refresca las consultas del libro (plan de ventas y saldos).", "args": []},
    {"id": "cubicar", "macro": "TrazWeb_Cubicar", "label": "Cubicar",
     "ayuda": "Cubica lo que esté cargado en 01_Entrada.", "args": []},
    {"id": "simular", "macro": "TrazWeb_Simular", "label": "Simular cubicaje",
     "ayuda": "Cubica sin escribir hojas ni trazabilidad.", "args": []},
    {"id": "visor", "macro": "TrazWeb_Visor", "label": "Generar visor 3D",
     "ayuda": "Genera el visor del último cubicaje y lo guarda en el pedido.",
     "args": [dict(PEDIDO, opcional=True)], "guarda_archivo": "visor"},
    {"id": "leer_pedido", "macro": "TrazWeb_LeerPedido", "label": "Leer pedido en SAP",
     "ayuda": "Escribe el pedido en 01_Entrada y extrae el picking de VL01N.", "args": [PEDIDO]},
    {"id": "crear_entregas", "macro": "TrazWeb_CrearEntregas", "label": "Crear entregas en SAP",
     "ayuda": "Crea una entrega por camión del cubicaje actual.", "args": []},
    {"id": "crear_grupos", "macro": "TrazWeb_CrearGrupos", "label": "Crear grupos en SAP",
     "ayuda": "Crea un grupo por camión con la referencia de la cita.", "args": []},
    {"id": "limpiar", "macro": "TrazWeb_Limpiar", "label": "Limpiar proceso",
     "ayuda": "Vacía las hojas de trabajo del libro.", "args": []},
    {"id": "eliminar_entrega", "macro": "TrazWeb_EliminarEntregaSAP", "label": "Eliminar entrega en SAP",
     "ayuda": "Borra la entrega en VL02N. Irreversible.", "args": [ENTREGA], "destructiva": True},
]
POR_ID = {a["id"]: a for a in CATALOGO}

_trabajos: dict[str, dict] = {}
_lock = threading.Lock()   # una macro a la vez: SAP GUI no tolera dos en paralelo


def habilitadas() -> list[dict]:
    if not settings.macros_workbook:
        return []
    return [{k: v for k, v in a.items() if k != "macro"}
            for a in CATALOGO if a["id"] in settings.acciones]


def disponibles() -> dict:
    return {"habilitado": bool(settings.macros_workbook and settings.acciones),
            "libro": Path(settings.macros_workbook).name if settings.macros_workbook else "",
            "acciones": habilitadas()}


def validar(accion_id: str, args: list[str]) -> tuple[dict, list[str]]:
    a = POR_ID.get(accion_id)
    if a is None or accion_id not in settings.acciones:
        raise PermissionError(f"La acción '{accion_id}' no está habilitada en .env.")
    if not settings.macros_workbook:
        raise RuntimeError("Falta MACROS_WORKBOOK en el archivo .env.")
    limpios: list[str] = []
    for i, spec in enumerate(a["args"]):
        valor = str(args[i]).strip() if i < len(args) else ""
        if not valor:
            if spec.get("opcional"):
                limpios.append("")
                continue
            raise ValueError(f"Falta {spec['etiqueta']}.")
        if not re.match(spec["patron"], valor):
            raise ValueError(f"{spec['etiqueta']} con formato inválido: {valor}")
        limpios.append(valor)
    return a, limpios


def lanzar(accion_id: str, args: list[str]) -> dict:
    a, limpios = validar(accion_id, args)
    if _lock.locked():
        raise RuntimeError("Ya hay una acción en ejecución. Espera a que termine.")
    tid = uuid.uuid4().hex[:12]
    _trabajos[tid] = {"id": tid, "accion": a["id"], "label": a["label"], "args": limpios,
                      "estado": "en_curso", "inicio": datetime.now().isoformat(timespec="seconds"),
                      "fin": "", "resultado": "", "error": "", "archivo": ""}
    threading.Thread(target=_correr, args=(tid, a, limpios), daemon=True).start()
    return _trabajos[tid]


def lanzar_python(accion_id: str, label: str, args: list[str], fn) -> dict:
    """Corre una función Python (por ejemplo, leer SAP directo) en la misma cola
    que las macros, para que nunca haya dos cosas usando SAP al mismo tiempo."""
    if _lock.locked():
        raise RuntimeError("Ya hay una acción en ejecución. Espera a que termine.")
    tid = uuid.uuid4().hex[:12]
    _trabajos[tid] = {"id": tid, "accion": accion_id, "label": label, "args": args,
                      "estado": "en_curso", "inicio": datetime.now().isoformat(timespec="seconds"),
                      "fin": "", "resultado": "", "error": "", "archivo": "", "datos": None,
                      "progreso": ""}

    def avance(texto: str):
        _trabajos[tid]["progreso"] = texto

    def correr():
        job = _trabajos[tid]
        with _lock:
            com = None
            try:
                import pythoncom
                pythoncom.CoInitialize()
                com = pythoncom
            except ImportError:
                pass
            try:
                job["datos"] = fn(avance)
                job.update(estado="ok")
            except Exception as e:  # noqa: BLE001
                job.update(estado="error", error=str(e)[:500])
            finally:
                job["fin"] = datetime.now().isoformat(timespec="seconds")
                if com:
                    com.CoUninitialize()

    threading.Thread(target=correr, daemon=True).start()
    return _trabajos[tid]


def trabajo(tid: str) -> dict | None:
    return _trabajos.get(tid)


def _correr(tid: str, a: dict, args: list[str]):
    job = _trabajos[tid]
    with _lock:
        try:
            import pythoncom            # pywin32, solo Windows
            import win32com.client
        except ImportError:
            job.update(estado="error", error="Ejecutar macros requiere Windows con pywin32 instalado.",
                       fin=datetime.now().isoformat(timespec="seconds"))
            return
        pythoncom.CoInitialize()
        try:
            xl = win32com.client.Dispatch("Excel.Application")   # se engancha al Excel abierto
            xl.Visible = True
            ruta = str(Path(settings.macros_workbook).resolve()).lower()
            wb = next((w for w in xl.Workbooks if str(w.FullName).lower() == ruta), None)
            if wb is None:
                wb = xl.Workbooks.Open(settings.macros_workbook)
            res = xl.Run(f"'{wb.Name}'!{a['macro']}", *args)
            res = "" if res is None else str(res)
            job["resultado"] = res[:500]
            if res.startswith("ERROR"):
                job.update(estado="error", error=res[:500])
            else:
                if a.get("guarda_archivo"):
                    job["archivo"] = _guardar(res, a["guarda_archivo"])
                job.update(estado="ok")
        except Exception as e:  # noqa: BLE001 - se informa tal cual al usuario
            job.update(estado="error", error=str(e)[:500])
        finally:
            job["fin"] = datetime.now().isoformat(timespec="seconds")
            pythoncom.CoUninitialize()


def _guardar(ruta_origen: str, tipo: str) -> str:
    """Copia a data/archivos el archivo que devolvió la macro."""
    origen = Path(ruta_origen)
    if not ruta_origen or not origen.exists():
        return ""
    DIR_ARCHIVOS.mkdir(parents=True, exist_ok=True)
    destino = DIR_ARCHIVOS / f"{tipo}_{uuid.uuid4().hex[:8]}{origen.suffix}"
    shutil.copy2(origen, destino)
    return destino.name
