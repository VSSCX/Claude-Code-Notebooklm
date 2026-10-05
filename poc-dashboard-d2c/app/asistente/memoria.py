"""Memoria del asistente: historial de preguntas compartido por todos los analistas, y aprendizaje con su valoracion.

Cada pregunta queda registrada con el plan que se armo y si se pudo responder. El pulgar arriba o abajo de cada respuesta
la valida o la descarta. Esa memoria se usa para:
  - repetir al instante una pregunta que ya funciono y fue validada (aunque las reglas cambien),
  - interpretar una pregunta que no se entiende como otra parecida que ya fue validada,
  - dar ejemplos validados a la IA (aprendizaje con pocos ejemplos) y evitar repetir una interpretacion rechazada,
  - olvidar palabras sueltas que no importaban (las de preguntas validadas) y sugerir las preguntas mas frecuentes.
Solo se guarda el texto de la pregunta y su plan (nunca las respuestas ni quien pregunto). En Vercel (sin disco) vive en memoria.
"""
from __future__ import annotations

import difflib
import json
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

from app.config import BASE_DIR, settings

from .texto import tokens

MAX = 2000                                     # preguntas que se recuerdan
_LOCK = threading.Lock()
_ENTRADAS: list[dict] = []
_POR_ID: dict[str, dict] = {}
_ARCHIVO: Path | None = None
_LISTO = False
_FORZADO: Path | None = None                    # solo las pruebas fijan otro archivo


def _ruta() -> Path | None:
    if _FORZADO is not None:
        return _FORZADO
    if settings.serverless:
        return None
    return Path(settings.asistente_historial) if settings.asistente_historial else BASE_DIR / "data" / "historial_asistente.jsonl"


def _cargar() -> None:
    global _LISTO, _ARCHIVO
    if _LISTO:
        return
    _LISTO, _ARCHIVO = True, _ruta()
    if not _ARCHIVO or not _ARCHIVO.exists():
        return
    try:
        for linea in _ARCHIVO.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(linea)
            except ValueError:
                continue
            if "util_de" in e:                                  # evento de valoracion
                if e["util_de"] in _POR_ID:
                    _POR_ID[e["util_de"]]["util"] = e.get("util")
            elif e.get("id") and e.get("qn"):
                _ENTRADAS.append(e)
                _POR_ID[e["id"]] = e
        del _ENTRADAS[:-MAX]
    except OSError:
        pass


def _escribir(obj: dict) -> None:
    if not _ARCHIVO:
        return
    try:
        _ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        with _ARCHIVO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except OSError:
        pass                                                   # sin permiso de escritura: sigue en memoria


def normalizar(q: str) -> str:
    return " ".join(tokens(q))


def registrar(q: str, plan: dict | None, ok: bool, via: str, seguimiento: bool = False, ignoradas: list | None = None) -> str:
    with _LOCK:
        _cargar()
        e = {"id": uuid.uuid4().hex[:10], "t": int(time.time()), "q": q[:300], "qn": normalizar(q), "plan": plan, "ok": bool(ok),
             "via": via, "seg": bool(seguimiento), "ign": ignoradas or [], "util": None}
        _ENTRADAS.append(e)
        _POR_ID[e["id"]] = e
        if len(_ENTRADAS) > MAX + 200:
            for viejo in _ENTRADAS[:200]:
                _POR_ID.pop(viejo["id"], None)
            del _ENTRADAS[:200]
        _escribir(e)
        return e["id"]


def valorar(id_: str, util: bool | None) -> bool:
    with _LOCK:
        _cargar()
        e = _POR_ID.get(str(id_))
        if e is None or util not in (True, False, None):
            return False
        e["util"] = util
        _escribir({"util_de": e["id"], "util": util, "t": int(time.time())})
        return True


def _validas(solo_validadas: bool):
    for e in reversed(_ENTRADAS):                              # las mas recientes primero
        if e["plan"] and not e["seg"] and e["util"] is not False and (e["util"] is True or (not solo_validadas and e["ok"])):
            yield e


def _similitud(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(jac, difflib.SequenceMatcher(None, a, b).ratio())


def exacta(qn: str) -> dict | None:
    """Una pregunta idéntica ya validada con el pulgar arriba."""
    with _LOCK:
        _cargar()
        return next((e for e in _validas(True) if e["qn"] == qn), None)


def parecidas(qn: str, n: int = 3, minimo: float = .6) -> list[dict]:
    """Preguntas ya validadas que se parecen a esta (mas parecida primero)."""
    with _LOCK:
        _cargar()
        vistas, res = set(), []
        for e in _validas(True):
            if e["qn"] in vistas:
                continue
            vistas.add(e["qn"])
            s = _similitud(qn, e["qn"])
            if s >= minimo:
                res.append((s, e))
        res.sort(key=lambda x: -x[0])
        return [e for _, e in res[:n]]


def rechazada(qn: str) -> bool:
    """La ultima vez que se hizo esta pregunta, la respuesta se marco como no util."""
    with _LOCK:
        _cargar()
        for e in reversed(_ENTRADAS):
            if e["qn"] == qn and e["util"] is not None:
                return e["util"] is False
        return False


def ruido() -> set[str]:
    """Palabras que aparecieron en preguntas validadas y que las reglas no usaron: no importan, se ignoran sin avisar."""
    with _LOCK:
        _cargar()
        return {w for e in _ENTRADAS if e["util"] is True for w in e.get("ign", [])}


def frecuentes(n: int = 6) -> list[str]:
    """Las preguntas que mas se repiten y funcionaron (o fueron validadas)."""
    with _LOCK:
        _cargar()
        c, texto = Counter(), {}
        for e in _ENTRADAS:
            if e["ok"] and e["util"] is not False and not e["seg"]:
                c[e["qn"]] += 2 if e["util"] else 1
                texto[e["qn"]] = e["q"]
        return [texto[k] for k, v in c.most_common(n) if v >= 2][:n]


def recientes(n: int = 6) -> list[str]:
    with _LOCK:
        _cargar()
        vistos, out = set(), []
        for e in reversed(_ENTRADAS):
            if e["ok"] and e["util"] is not False and not e["seg"] and e["qn"] not in vistos:
                vistos.add(e["qn"])
                out.append(e["q"])
                if len(out) >= n:
                    break
        return out


def estadisticas() -> dict:
    """Para quien mantiene el programa: cuanto se usa, cuanto se entiende y que no se entendio (para mejorar las reglas)."""
    with _LOCK:
        _cargar()
        total = len(_ENTRADAS)
        ok = sum(e["ok"] for e in _ENTRADAS)
        no = Counter(e["q"] for e in _ENTRADAS if not e["ok"])
        mal = Counter(e["q"] for e in _ENTRADAS if e["util"] is False)
        return {"preguntas": total, "respondidas": ok, "utiles": sum(e["util"] is True for e in _ENTRADAS),
                "no_utiles": sum(e["util"] is False for e in _ENTRADAS), "guardado_en": str(_ARCHIVO) if _ARCHIVO else None,
                "no_entendidas": no.most_common(20), "marcadas_no_utiles": mal.most_common(20)}


def reiniciar_para_pruebas(archivo: str) -> None:
    """Vacia la memoria y la vuelve a leer de `archivo` (para probar que el historial sobrevive a un reinicio)."""
    global _LISTO, _FORZADO
    with _LOCK:
        _ENTRADAS.clear()
        _POR_ID.clear()
        _FORZADO, _LISTO = Path(archivo), False
