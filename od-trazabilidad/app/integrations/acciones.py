"""Trabajos de la plataforma que usan SAP (analizar, crear entregas y grupos, borrar…).

Todo corre desde la plataforma, con la sesión de SAP GUI del usuario que tiene abierto run.bat
(SAP GUI scripting necesita esa sesión interactiva). Se ejecuta una acción a la vez, porque SAP GUI
no tolera dos en paralelo, y el avance se consulta por /api/acciones/trabajos/<id>.
"""
import threading
import uuid
from datetime import datetime

from ..config import BASE_DIR

DIR_ARCHIVOS = BASE_DIR / "data" / "archivos"

_trabajos: dict[str, dict] = {}
_lock = threading.Lock()   # una acción a la vez: SAP GUI no tolera dos en paralelo
_reserva = threading.Lock()
_ocupado = [False]
MAX_TRABAJOS = 50          # los más viejos se olvidan: la lista no crece sin fin


def _reservar() -> None:
    """Deja pasar a una sola acción. Revisar y marcar va junto: dos clics casi a la vez
    ya no pueden colarse los dos (antes se miraba el candado y el hilo lo tomaba después)."""
    with _reserva:
        if _ocupado[0]:
            raise RuntimeError("Ya hay una acción en ejecución. Espera a que termine.")
        _ocupado[0] = True


def _liberar() -> None:
    with _reserva:
        _ocupado[0] = False


def _registrar(job: dict) -> None:
    _trabajos[job["id"]] = job
    while len(_trabajos) > MAX_TRABAJOS:
        _trabajos.pop(next(iter(_trabajos)))


def lanzar_python(accion_id: str, label: str, args: list[str], fn) -> dict:
    """Corre una función Python (por ejemplo, leer SAP directo) en la cola de trabajos,
    para que nunca haya dos cosas usando SAP al mismo tiempo."""
    _reservar()
    tid = uuid.uuid4().hex[:12]
    _registrar({"id": tid, "accion": accion_id, "label": label, "args": args,
                "estado": "en_curso", "inicio": datetime.now().isoformat(timespec="seconds"),
                "fin": "", "resultado": "", "error": "", "datos": None,
                "progreso": ""})

    def avance(texto: str):
        _trabajos[tid]["progreso"] = texto

    def correr():
        job = _trabajos[tid]
        try:
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
        finally:
            _liberar()

    try:
        threading.Thread(target=correr, daemon=True).start()
    except BaseException:
        _liberar()
        raise
    return _trabajos[tid]


def trabajo(tid: str) -> dict | None:
    return _trabajos.get(tid)
