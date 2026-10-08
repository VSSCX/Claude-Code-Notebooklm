"""Bitacora de auditoria con cadena de hashes: cada registro incluye el hash del anterior, asi que borrar o editar uno rompe la cadena
y `verificar()` lo detecta. Registra quien entro, quien exporto, que se pregunto al asistente y que datos se cargaron.

Local: data/auditoria.jsonl (o AUDITORIA_ARCHIVO). En Vercel el disco no persiste: cada registro sale ademas por los logs de la funcion
(una linea JSON con prefijo AUDITORIA), que se pueden enviar a un Log Drain. No se guardan claves ni datos de pedidos."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .config import BASE_DIR, settings

_LOCK = threading.Lock()
_ESTADO: dict = {"ultimo": "0" * 64, "n": 0, "listo": False}
_MEMORIA: list[dict] = []          # ultimos registros de esta instancia (Vercel)
_FORZADO: Path | None = None


def _archivo() -> Path | None:
    if _FORZADO is not None:
        return _FORZADO
    if settings.serverless:
        return Path(settings.auditoria_archivo) if settings.auditoria_archivo else None
    return Path(settings.auditoria_archivo) if settings.auditoria_archivo else BASE_DIR / "data" / "auditoria.jsonl"


def _hash(reg: dict) -> str:
    base = {k: v for k, v in reg.items() if k != "hash"}
    return hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _iniciar() -> None:
    if _ESTADO["listo"]:
        return
    _ESTADO["listo"] = True
    a = _archivo()
    if a and a.exists():
        try:
            for linea in a.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    _ESTADO["ultimo"], _ESTADO["n"] = json.loads(linea)["hash"], _ESTADO["n"] + 1
        except Exception:  # noqa: BLE001  (un archivo danado se reporta en verificar(), no impide seguir registrando)
            pass


def registrar(evento: str, usuario: str | None = None, **detalle) -> dict:
    """Agrega un registro. Nunca lanza: la bitacora no debe tumbar la aplicacion."""
    try:
        with _LOCK:
            _iniciar()
            reg = {"n": _ESTADO["n"] + 1, "t": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z", "evento": evento,
                   "usuario": usuario or "-", "detalle": {k: v for k, v in detalle.items() if v is not None}, "prev": _ESTADO["ultimo"]}
            reg["hash"] = _hash(reg)
            _ESTADO.update(ultimo=reg["hash"], n=reg["n"])
            _MEMORIA.append(reg)
            del _MEMORIA[:-500]
            a = _archivo()
            if a:
                a.parent.mkdir(parents=True, exist_ok=True)
                with a.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(reg, ensure_ascii=False) + "\n")
            if settings.serverless:
                print("AUDITORIA " + json.dumps(reg, ensure_ascii=False), flush=True)
            return reg
    except Exception:  # noqa: BLE001
        return {}


def leer(n: int = 100) -> list[dict]:
    a = _archivo()
    with _LOCK:
        if a and a.exists():
            lineas = a.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(x) for x in lineas if x.strip()][::-1]
        return _MEMORIA[-n:][::-1]


def verificar() -> dict:
    """Recorre toda la cadena. -> {ok, registros, error}. Si alguien edito o borro un registro, indica donde."""
    a = _archivo()
    if not a or not a.exists():
        return {"ok": True, "registros": len(_MEMORIA), "error": None, "nota": "Sin archivo de bitacora (solo memoria/logs)."}
    prev, n = "0" * 64, 0
    for i, linea in enumerate(a.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except ValueError:
            return {"ok": False, "registros": n, "error": f"línea {i}: no es JSON"}
        if r.get("prev") != prev or r.get("hash") != _hash(r):
            return {"ok": False, "registros": n, "error": f"línea {i}: la cadena se rompe (registro modificado o faltante)"}
        prev, n = r["hash"], n + 1
    return {"ok": True, "registros": n, "error": None}


def reiniciar_para_pruebas(archivo: str) -> None:
    global _FORZADO
    with _LOCK:
        _FORZADO = Path(archivo)
        _ESTADO.update(ultimo="0" * 64, n=0, listo=False)
        _MEMORIA.clear()
