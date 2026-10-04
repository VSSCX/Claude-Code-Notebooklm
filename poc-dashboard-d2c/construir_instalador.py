# -*- coding: utf-8 -*-
"""Genera POC_Dashboard.py (el instalador todo-en-uno) a partir de esta carpeta.

Uso:   py construir_instalador.py [--version 2.7] [--base POC_Dashboard.v2.6.original.py] [--salida POC_Dashboard.py]

Toma el codigo del instalador anterior (todo lo que NO es el paquete), le cambia la version, el paquete
comprimido y el checksum, y deja el archivo listo para repartir. Los archivos de texto van como texto;
los binarios (fuentes, imagenes) van en base64. Se incluye solo lo que necesita el dashboard para correr.
"""
import argparse
import base64
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BINARIOS = {".woff2", ".png", ".ico"}
RAIZ = [".env.example", ".gitignore", "requirements.txt", "run.bat"]
CARPETAS = ["app", "public"]


def reunir():
    rutas = [AQUI / r for r in RAIZ]
    for c in CARPETAS:
        rutas += sorted(p for p in (AQUI / c).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    paquete = {}
    for p in rutas:
        rel = p.relative_to(AQUI).as_posix()
        if p.suffix.lower() in BINARIOS:
            paquete[rel] = {"b64": base64.b64encode(p.read_bytes()).decode("ascii")}
        else:
            paquete[rel] = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return paquete


COPIAR_NUEVO = '''def copiar_archivos(destino, archivos):
    destino.mkdir(parents=True, exist_ok=True)
    nuevos = cambiados = iguales = 0
    for ruta, cont in archivos.items():
        dst = destino / ruta
        if dst.name == ".env":
            continue  # nunca se pisan las credenciales
        dst.parent.mkdir(parents=True, exist_ok=True)
        binario = isinstance(cont, dict)  # fuentes e imagenes viajan en base64
        datos = base64.b64decode(cont["b64"]) if binario else None
        if dst.exists():
            if binario:
                igual = dst.read_bytes() == datos
            else:
                igual = dst.read_text(encoding="utf-8", errors="replace").replace("\\r\\n", "\\n") == cont
            if igual:
                iguales += 1
                continue
            cambiados += 1
        else:
            nuevos += 1
        if binario:
            dst.write_bytes(datos)
        elif ruta.startswith("public/vendor/"):
            dst.write_bytes(cont.encode("utf-8"))  # librerias minificadas: tal cual, sin cambiar saltos de linea
        else:
            dst.write_text(cont, encoding="utf-8")
    ok(f"{nuevos} archivos nuevos, {cambiados} actualizados, {iguales} sin cambios")
    ok(f"Carpeta: {destino}")
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2.7")
    ap.add_argument("--base", default=str(AQUI / "POC_Dashboard.v2.6.original.py"))
    ap.add_argument("--salida", default=str(AQUI / "POC_Dashboard.py"))
    a = ap.parse_args()

    src = Path(a.base).read_text(encoding="utf-8")
    raw = json.dumps(reunir(), ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    lineas = "\n".join(f'    "{b64[i:i + 108]}"' for i in range(0, len(b64), 108))

    src, n = re.subn(r'VERSION = "[^"]*"', f'VERSION = "{a.version}"', src, count=1)
    assert n == 1, "no encontre VERSION"
    src, n = re.subn(r'SHA256 = "[0-9a-f]{64}"', f'SHA256 = "{hashlib.sha256(raw).hexdigest()}"', src, count=1)
    assert n == 1, "no encontre SHA256"
    src, n = re.subn(r"PAQUETE = \(\n.*?\n\)\n", lambda m: f"PAQUETE = (\n{lineas}\n)\n", src, count=1, flags=re.S)
    assert n == 1, "no encontre PAQUETE"
    src, n = re.subn(r"def copiar_archivos\(destino, archivos\):\n.*?\n    ok\(f\"Carpeta: \{destino\}\"\)\n",
                     lambda m: COPIAR_NUEVO, src, count=1, flags=re.S)
    assert n == 1, "no encontre copiar_archivos"
    if "Novedades" not in src:
        src = src.replace('Opciones:  --demo', 'Novedades v' + a.version + ': pantalla rehecha (sistema "etiqueta logistica"), tema claro/oscuro,\n'
                          'modo TV, fuentes y librerias locales (sin internet) y actualizacion en vivo sin perder filtros ni foco.\n\n'
                          'Opciones:  --demo', 1)
    Path(a.salida).write_text(src, encoding="utf-8")
    print(f"{a.salida}: v{a.version}, {len(raw):,} bytes de proyecto, {len(src):,} bytes de instalador, sha256 {hashlib.sha256(raw).hexdigest()[:12]}")


if __name__ == "__main__":
    sys.exit(main())
