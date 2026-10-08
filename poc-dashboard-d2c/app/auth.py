"""Acceso: usuarios con rol (lector < analista < admin), sesion firmada, bloqueo por intentos y proteccion CSRF.

Claves: PBKDF2-SHA256 con sal (nunca en claro). Sesion: cookie HttpOnly + SameSite=Strict firmada con HMAC (SESSION_SECRET) que vence sola.
Si hay datos reales en un servidor publico (Vercel con snapshot) y no hay usuarios, el acceso queda CERRADO (falla segura)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from urllib.parse import urlparse

from .config import settings

ROLES = {"lector": 1, "analista": 2, "admin": 3}
COOKIE = "d2c_sesion"
ITER = 240_000
_SECRETO_LOCAL = secrets.token_hex(32)           # si no hay SESSION_SECRET (solo local): las sesiones duran hasta reiniciar
_LOCK = threading.Lock()
_FALLOS: dict[str, list[float]] = {}
_USO: dict[str, list[float]] = {}
MAX_FALLOS, VENTANA_FALLOS = 5, 900

# ruta (prefijo) -> rol minimo. Lo que no aparece exige "lector". Publicas: /api/login, /api/salud.
PERMISOS = (("/api/auditoria", "admin"), ("/api/diagnostico", "admin"), ("/api/chat/historial", "admin"), ("/api/chat/aprendizaje", "admin"),
            ("/api/calidad", "analista"), ("/api/linaje", "analista"), ("/api/chat/valorar", "analista"),
            ("/api/ventas/exportar", "analista"), ("/api/pedidos/exportar", "analista"))
PUBLICAS = ("/api/login", "/api/salud")
LIMITES = {"/api/chat": 30, "/api/ventas/exportar": 20, "/api/pedidos/exportar": 20}      # por usuario y minuto


# ------------------------------------------------------------------ claves y usuarios
def hash_clave(clave: str, sal: bytes | None = None, iteraciones: int = ITER) -> str:
    sal = sal or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2${iteraciones}${base64.b64encode(sal).decode()}${base64.b64encode(h).decode()}"


def _verificar(clave: str, almacenado: str) -> bool:
    try:
        _, it, sal, h = almacenado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), base64.b64decode(sal), int(it))
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def usuarios() -> dict[str, dict]:
    out = {}
    for parte in settings.dash_usuarios.split(";"):
        p = parte.strip().split(":")
        if len(p) == 3 and p[2].strip() in ROLES and p[1].startswith("pbkdf2$"):
            out[p[0].strip().lower()] = {"hash": p[1].strip(), "rol": p[2].strip()}
    return out


_FALSO = hash_clave("no-existe", b"0" * 16, 1000)       # para gastar el mismo tiempo cuando el usuario no existe


def requerida() -> bool:
    if settings.auth_requerida in ("1", "true", "si"):
        return True
    if settings.auth_requerida in ("0", "false", "no"):
        return False
    return bool(usuarios()) or (settings.fuente_snapshot and settings.serverless)


def problema_de_configuracion() -> str | None:
    """Por que no se puede entrar aunque se quiera (se muestra en la pantalla de acceso)."""
    if not requerida():
        return None
    if not usuarios():
        return "El acceso está activado pero no hay usuarios configurados (DASH_USUARIOS). Créalos con seguridad_admin.py."
    if settings.serverless and len(settings.session_secret) < 32:
        return "Falta SESSION_SECRET (mínimo 32 caracteres) en las variables de entorno."
    return None


# ------------------------------------------------------------------ sesion
def _secreto() -> bytes:
    return (settings.session_secret or _SECRETO_LOCAL).encode("utf-8")


def _firmar(datos: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secreto(), datos, hashlib.sha256).digest()).decode().rstrip("=")


def crear_sesion(usuario: str, rol: str) -> str:
    cuerpo = base64.urlsafe_b64encode(json.dumps({"u": usuario, "r": rol, "e": int(time.time()) + settings.sesion_horas * 3600,
                                                  "n": secrets.token_hex(6)}).encode()).decode().rstrip("=")
    return cuerpo + "." + _firmar(cuerpo.encode())


def leer_sesion(token: str | None) -> dict | None:
    try:
        cuerpo, firma = (token or "").split(".")
        if not hmac.compare_digest(firma, _firmar(cuerpo.encode())):
            return None
        d = json.loads(base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)))
        if d["e"] < time.time() or d["r"] not in ROLES or d["u"] not in usuarios():      # usuario dado de baja = sesion invalida
            return None
        return {"usuario": d["u"], "rol": usuarios()[d["u"]]["rol"]}                    # el rol vigente manda, no el de la cookie
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ intentos, limites, CSRF
def bloqueado(clave: str) -> bool:
    with _LOCK:
        t = [x for x in _FALLOS.get(clave, []) if time.time() - x < VENTANA_FALLOS]
        _FALLOS[clave] = t
        return len(t) >= MAX_FALLOS


def anotar_fallo(clave: str) -> None:
    with _LOCK:
        _FALLOS.setdefault(clave, []).append(time.time())


def limpiar_fallos(clave: str) -> None:
    with _LOCK:
        _FALLOS.pop(clave, None)


def iniciar_sesion(usuario: str, clave: str) -> dict | None:
    u = usuarios().get((usuario or "").strip().lower())
    ok = _verificar(clave or "", u["hash"] if u else _FALSO)
    return {"usuario": usuario.strip().lower(), "rol": u["rol"]} if (u and ok) else None


def excede_limite(usuario: str, ruta: str) -> bool:
    tope = LIMITES.get(ruta)
    if not tope:
        return False
    k, ahora = f"{usuario}|{ruta}", time.time()
    with _LOCK:
        t = [x for x in _USO.get(k, []) if ahora - x < 60]
        t.append(ahora)
        _USO[k] = t
        return len(t) > tope


def origen_valido(metodo: str, origin: str | None, host: str | None) -> bool:
    """CSRF: una peticion que cambia algo y trae Origin debe venir del mismo sitio."""
    if metodo in ("GET", "HEAD", "OPTIONS") or not origin:
        return True
    return urlparse(origin).netloc == (host or "")


def rol_minimo(ruta: str) -> str:
    for prefijo, rol in PERMISOS:
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return rol
    return "lector"


def permitido(rol: str, ruta: str) -> bool:
    return ROLES.get(rol, 0) >= ROLES[rol_minimo(ruta)]
