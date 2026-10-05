"""Cuentas por analista: claves con hash, sesiones con caducidad y bloqueo por intentos fallidos.

Dos modos, según haya o no cuentas creadas:
- **abierto**: sin cuentas (un PC, una persona). Como siempre: se escribe el nombre y, si el .env trae
  CLAVE_ACCESO, esa clave.
- **cuentas**: cada analista entra con su usuario y clave; el historial y los errores quedan a su nombre.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import SesionWeb, Usuario, ahora

COOKIE = "od_sesion"
ROLES = ("analista", "admin")
ITERACIONES = 240_000
MAX_INTENTOS, BLOQUEO_SEG = 5, 300
_fallos: dict[str, list[float]] = {}            # usuario|ip -> instantes de intentos fallidos
_modo_cache: dict = {"t": 0.0, "cuentas": None}


# ---------------------------------------------------------------- claves
def hashear(clave: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, ITERACIONES)
    return f"pbkdf2${ITERACIONES}${sal.hex()}${h.hex()}"


def verificar(clave: str, guardado: str) -> bool:
    try:
        _, it, sal, h = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, AttributeError):
        return False


def validar_clave_nueva(clave: str, usuario: str = "") -> str:
    """Devuelve el motivo si la clave no sirve, o '' si está bien."""
    if len(clave or "") < 8:
        return "La clave debe tener al menos 8 caracteres."
    if not re.search(r"[A-Za-z]", clave) or not re.search(r"\d", clave):
        return "La clave debe mezclar letras y números."
    if usuario and usuario.lower() in clave.lower():
        return "La clave no puede contener el usuario."
    return ""


def clave_temporal() -> str:
    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"          # sin caracteres que se confunden (l, 1, o, 0)
    return "".join(secrets.choice(alfabeto) for _ in range(4)) + "-" + "".join(secrets.choice(alfabeto) for _ in range(4)) + secrets.choice("23456789")


def nombre_usuario(texto: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "", str(texto or "").strip().lower())[:40]


# ---------------------------------------------------------------- modo
def hay_cuentas(s: Session, fresco: bool = False) -> bool:
    """¿Existe alguna cuenta activa? Se recuerda 20 s para no consultar en cada petición."""
    if not fresco and _modo_cache["cuentas"] is not None and time.time() - _modo_cache["t"] < 20:
        return _modo_cache["cuentas"]
    n = s.scalar(select(func.count()).select_from(Usuario).where(Usuario.activo.is_(True))) or 0
    _modo_cache.update(t=time.time(), cuentas=n > 0)
    return n > 0


def olvidar_modo() -> None:
    _modo_cache["cuentas"] = None


def exige_entrar(s: Session) -> bool:
    return hay_cuentas(s) or settings.autenticacion == "obligatoria"


def crear_admin_inicial(s: Session) -> str:
    """ADMIN_INICIAL=usuario:clave:Nombre. Solo si todavía no hay ninguna cuenta."""
    cfg = settings.admin_inicial.strip()
    if not cfg or s.scalar(select(func.count()).select_from(Usuario)):
        return ""
    partes = cfg.split(":", 2)
    if len(partes) < 2:
        return ""
    u, clave = nombre_usuario(partes[0]), partes[1]
    if not u or validar_clave_nueva(clave, u):
        return ""
    s.add(Usuario(usuario=u, nombre=(partes[2] if len(partes) > 2 else u).strip()[:60] or u, rol="admin",
                  clave_hash=hashear(clave)))
    s.commit()
    olvidar_modo()
    return u


# ---------------------------------------------------------------- bloqueo por intentos
def _clave_fallos(usuario: str, ip: str) -> str:
    return f"{usuario}|{ip}"


def segundos_bloqueado(usuario: str, ip: str) -> int:
    ahora_t = time.time()
    lista = [t for t in _fallos.get(_clave_fallos(usuario, ip), []) if ahora_t - t < BLOQUEO_SEG]
    _fallos[_clave_fallos(usuario, ip)] = lista
    if len(lista) >= MAX_INTENTOS:
        return int(BLOQUEO_SEG - (ahora_t - lista[0])) + 1
    return 0


def anotar_fallo(usuario: str, ip: str) -> int:
    k = _clave_fallos(usuario, ip)
    _fallos.setdefault(k, []).append(time.time())
    return max(0, MAX_INTENTOS - len(_fallos[k]))


def limpiar_fallos(usuario: str, ip: str) -> None:
    _fallos.pop(_clave_fallos(usuario, ip), None)


# ---------------------------------------------------------------- sesiones
def _huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def abrir_sesion(s: Session, u: Usuario, ip: str = "", agente: str = "") -> str:
    token = secrets.token_urlsafe(32)
    s.add(SesionWeb(token_hash=_huella(token), usuario_id=u.id, ip=ip[:60], agente=agente[:200]))
    u.ultimo_acceso = ahora()
    s.commit()
    return token


def usuario_de(s: Session, token: str) -> Usuario | None:
    """El usuario de una sesión vigente. Cada uso renueva la caducidad por inactividad."""
    if not token:
        return None
    se = s.get(SesionWeb, _huella(token))
    if se is None:
        return None
    limite = timedelta(hours=max(1, settings.sesion_horas))
    if ahora() - se.vista > limite:
        s.delete(se)
        s.commit()
        return None
    u = s.get(Usuario, se.usuario_id)
    if u is None or not u.activo:
        return None
    if ahora() - se.vista > timedelta(minutes=5):           # no se escribe en cada petición
        se.vista = ahora()
        s.commit()
    return u


def cerrar_sesion(s: Session, token: str) -> None:
    s.execute(delete(SesionWeb).where(SesionWeb.token_hash == _huella(token)))
    s.commit()


def cerrar_sesiones_de(s: Session, usuario_id: int, salvo: str = "") -> int:
    q = delete(SesionWeb).where(SesionWeb.usuario_id == usuario_id)
    if salvo:
        q = q.where(SesionWeb.token_hash != _huella(salvo))
    n = s.execute(q).rowcount or 0
    s.commit()
    return n


def purgar_sesiones(s: Session) -> None:
    s.execute(delete(SesionWeb).where(SesionWeb.vista < ahora() - timedelta(hours=max(1, settings.sesion_horas))))
    s.commit()
