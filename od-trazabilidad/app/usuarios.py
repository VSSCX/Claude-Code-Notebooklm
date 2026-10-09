"""Quién está usando la plataforma.

Dos cosas distintas:
- **Usuario**: el nombre que la persona escribe al entrar. Queda en el historial de cada
  entrega, para saber quién hizo qué. Sin nombre no se puede escribir nada.
- **Clave**: opcional. Si en el .env hay CLAVE_ACCESO, la plataforma la pide antes de
  mostrar nada. Sirve cuando deja de correr solo en el PC de una persona.
"""
from __future__ import annotations

import re
import secrets

from fastapi import Header, HTTPException, Request

from .config import settings

_sesiones: set[str] = set()
CABECERA = "x-usuario"


def limpio(nombre: str) -> str:
    n = re.sub(r"\s+", " ", str(nombre or "")).strip()
    return n[:40]


def usuario_del_sistema() -> str:
    """Quién es en Windows la persona que abrió la plataforma en su PC. Reemplaza la pregunta «¿cuál es tu nombre?»:
    el historial de cada entrega queda a nombre de esa cuenta sin que nadie tenga que escribir nada."""
    import getpass
    try:
        return limpio(getpass.getuser())
    except Exception:  # noqa: BLE001
        return ""


def requiere_clave() -> bool:
    return bool(getattr(settings, "clave_acceso", ""))


def entrar(clave: str, usuario: str) -> str:
    usuario = limpio(usuario) or usuario_del_sistema()
    if not usuario:
        raise HTTPException(422, "No se pudo saber quién eres: escribe tu nombre para entrar.")
    if requiere_clave() and not secrets.compare_digest(str(clave).encode(), settings.clave_acceso.encode()):
        raise HTTPException(401, "Clave incorrecta.")
    token = secrets.token_hex(16)
    _sesiones.add(token)
    return token


def sesion_valida(token: str) -> bool:
    return not requiere_clave() or token in _sesiones


def actual(x_usuario: str = Header(default="")) -> str:
    """Nombre de quien hace la acción; va en el historial."""
    return limpio(x_usuario) or "sin nombre"


def verificar(request: Request) -> None:
    """Deja pasar si no hay clave configurada o si la sesión es válida."""
    if not requiere_clave():
        return
    token = request.cookies.get("sesion", "")
    if not sesion_valida(token):
        raise HTTPException(401, "Sesión no iniciada.")
