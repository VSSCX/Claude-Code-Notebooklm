# -*- coding: utf-8 -*-
"""Auditoria automatica de "listo para Vercel". Uso:  python verificar_vercel.py

Comprueba lo que se puede comprobar sin desplegar: configuracion, dependencias, archivos estaticos,
cabeceras de seguridad y el comportamiento del servidor tal como corre en Vercel (VERCEL=1: solo demo,
sin hilo en segundo plano, sin rutas de diagnostico). Sale con codigo 1 si algo falla.
Lo que NO puede comprobar (build real, limites del plan, red) esta en VERCEL.md.
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
fallos = []


def chequeo(nombre, ok, detalle=""):
    print(("  [OK]   " if ok else "  [FALLA] ") + nombre + (f"  ->  {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre)


def leer(p):
    return (AQUI / p).read_text(encoding="utf-8")


print("1. Configuracion de Vercel")
cfg = json.loads(leer("vercel.json"))
chequeo("vercel.json es JSON valido", True)
chequeo("las rutas /api/* van a la funcion api/index.py",
        any(r["source"] == "/api/(.*)" and r["destination"] == "/api/index" for r in cfg.get("rewrites", [])))
chequeo("api/index.py expone la variable app", re.search(r"from app\.main import app", leer("api/index.py")) is not None)
from app.seguridad import CABECERAS  # noqa: E402
glob = next((h["headers"] for h in cfg["headers"] if h["source"] == "/(.*)"), [])
dic = {h["key"]: h["value"] for h in glob}
chequeo("vercel.json declara las mismas cabeceras de seguridad que el servidor",
        all(dic.get(k) == v for k, v in CABECERAS.items()),
        str([k for k, v in CABECERAS.items() if dic.get(k) != v]))
chequeo("HSTS declarado", "Strict-Transport-Security" in dic)
chequeo("version de Python fijada (.python-version)", (AQUI / ".python-version").read_text().strip() != "")

print("2. Dependencias")
req = leer("requirements.txt").splitlines()
sin_marca = [l for l in req if l.strip().lower().startswith("pyodbc") and "sys_platform" not in l]
chequeo("pyodbc solo se instala en Windows (en Vercel/Linux no compila ni se usa)", not sin_marca, str(sin_marca))
chequeo("requirements.txt no trae paquetes de desarrollo", not any(re.match(r"(pytest|playwright|black|ruff)", l) for l in req))

print("3. Archivos estaticos (public/)")
pub = AQUI / "public"
for f in ["index.html", "css/app.css", "js/app.js", "js/tema.js", "js/iconos.js", "js/detalle.js", "js/asistente.js", "vendor/chart.umd.min.js", "vendor/morphdom.min.js",
          "fonts/plus-jakarta-sans-latin.woff2", "fonts/jetbrains-mono-latin.woff2", "img/logo.png"]:
    chequeo(f"existe public/{f}", (pub / f).exists())
html = leer("public/index.html")
chequeo("index.html no tiene scripts en linea ni manejadores on*=",
        not re.search(r"<script(?![^>]*\bsrc=)", html) and not re.search(r"\son[a-z]+\s*=", html))
externo = []
for f in ["public/index.html", "public/css/app.css", "public/js/app.js", "public/js/tema.js", "public/js/detalle.js", "public/js/asistente.js"]:
    for m in re.finditer(r"https?://[^\s\"')]+", leer(f)):
        if "w3.org" not in m.group(0):
            externo.append(f"{f}: {m.group(0)[:60]}")
chequeo("ninguna fuente, libreria ni imagen se pide a internet (todo local)", not externo, "; ".join(externo[:3]))
raya = [f for f in ["public/index.html", "public/css/app.css", "public/js/app.js", "public/js/iconos.js", "public/js/detalle.js", "public/js/asistente.js"] if "\u2014" in leer(f) or "\u2013" in leer(f)]
chequeo("sin rayas largas (em/en dash) en la interfaz (regla de taste-skill: solo guion normal)", not raya, str(raya))
tam = sum(p.stat().st_size for p in pub.rglob("*") if p.is_file())
chequeo(f"public/ pesa {tam/1024:.0f} KB (< 5 MB)", tam < 5 * 1024 * 1024)

print("4. Servidor como corre en Vercel (VERCEL=1)")
s = socket.socket(); s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]; s.close()
env = dict(os.environ, VERCEL="1", PYTHONPATH=str(AQUI))
env.pop("DEMO", None)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.index:app", "--port", str(puerto)], cwd=str(AQUI),
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base = f"http://127.0.0.1:{puerto}"


def llamar(ruta, metodo="GET", cuerpo=None):
    req = urllib.request.Request(base + ruta, method=metodo, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


try:
    for _ in range(60):
        try:
            llamar("/api/config"); break
        except Exception:
            time.sleep(.5)
    st, h, b = llamar("/api/config"); c = json.loads(b)
    chequeo("modo DEMO forzado (nunca consulta las bases)", c.get("demo") is True)
    chequeo("no ofrece simular pedidos (el estado vive en memoria de cada instancia)", c.get("simulable") is False)
    chequeo("el navegador consulta cada 30 s, no cada 2 s", c.get("poll") == 30, str(c.get("poll")))
    t0 = time.time(); st, h, b = llamar("/api/dashboard", "POST", {}); dur = time.time() - t0
    d = json.loads(b)
    chequeo(f"/api/dashboard responde con datos ({dur:.1f} s la primera vez, limite de la funcion 60 s)", st == 200 and "kpi" in d and dur < 45)
    chequeo("/api/* no se guarda en cache (Cache-Control: no-store)", h.get("cache-control") == "no-store")
    chequeo("cabeceras de seguridad presentes en las respuestas del servidor",
            all(h.get(k.lower()) == v or h.get(k) == v for k, v in CABECERAS.items()))
    st, h, b = llamar("/api/version"); v = json.loads(b)
    chequeo("no hay hilo de monitoreo en segundo plano", v.get("revisado") is None, str(v.get("revisado")))
    chequeo("/api/diagnostico no esta publicado", llamar("/api/diagnostico")[0] == 404)
    chequeo("/api/demo/pedido no esta publicado", llamar("/api/demo/pedido", "POST")[0] == 404)
    st, h, b = llamar("/api/pedido/3500002")
    d2 = json.loads(b) if st == 200 else {}
    chequeo("/api/pedido/{sequence} entrega cabecera y lineas del pedido", st == 200 and d2.get("lineas") and d2["lineas"][0].get("descripcion"))
    chequeo("/api/pedido rechaza un Sequence que no es numerico", llamar("/api/pedido/abc")[0] == 400 and llamar("/api/pedido/9999999999")[0] == 404)
    st, h, b = llamar("/api/chat", "POST", {"pregunta": "cuantas unidades del refrigerador med 165b cayeron hoy"})
    r = json.loads(b) if st == 200 else {}
    chequeo("/api/chat responde con reglas (sin IA) y calcula una cifra", st == 200 and r.get("ok") and r.get("via") == "reglas" and r.get("valor", 0) > 0, str(r)[:120])
    chequeo("/api/chat tolera cuerpos invalidos", llamar("/api/chat", "POST", ["x"])[0] == 200 and llamar("/api/chat", "POST", {"pregunta": "x" * 5000, "previo": "no"})[0] == 200)
    chequeo("/docs y /openapi.json no estan publicados", llamar("/docs")[0] == 404 and llamar("/openapi.json")[0] == 404)
    st, h, b = llamar("/api/dashboard", "POST", ["no", "es", "un", "objeto"])
    chequeo("un cuerpo invalido no rompe el servidor", st in (200, 422, 503))
finally:
    srv.terminate()

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} falla(s): " + "; ".join(fallos))
    sys.exit(1)
print("RESULTADO: todo en orden")
