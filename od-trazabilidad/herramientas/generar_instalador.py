"""Regenera crear_proyecto.py (el instalador de un solo archivo) a partir de esta carpeta.

Uso, desde la carpeta del proyecto:
    py herramientas\\generar_instalador.py RUTA\\crear_proyecto.py

Toma el crear_proyecto.py que ya tienes como plantilla: conserva su bloque de conexión
a SQL Server y la lógica de instalación, y reemplaza solo los archivos incluidos. Los
archivos de texto van en ARCHIVOS y los binarios (fuentes) en BINARIOS, en base64.
Solo usa la biblioteca estándar.

Con --sin-cuentas el instalador sale sin los archivos de servidor y cuentas (docs\\SERVIDOR.md, servidor.bat,
herramientas\\restablecer_clave.py): es el que se reparte a los analistas que usan la plataforma en su propio PC.
"""
import base64
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIR_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "data", "node_modules", ".impeccable"}
EXCLUIR_ARCHIVOS = {".env", "xlsx.full.min.js", "crear_proyecto.py"}
SOLO_SERVIDOR = {"docs/SERVIDOR.md", "docs/PENDIENTES.md", "servidor.bat", "herramientas/restablecer_clave.py"}   # PENDIENTES: notas del equipo
CONSERVAR_VACIOS = {".gitkeep"}          # data/.gitkeep y casos/.gitkeep crean las carpetas
BINARIOS_EXT = {".woff2", ".woff", ".png", ".jpg", ".ico", ".xls"}

ESCRIBIR_BINARIOS = '''    for rel, b64 in BINARIOS.items():
        ruta = DESTINO / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(base64.b64decode(b64))
    print(f"{len(ARCHIVOS) + len(BINARIOS)} archivos creados en {DESTINO}")'''


def recolectar(sin_cuentas: bool = False):
    texto, binarios = {}, {}
    for ruta in sorted(RAIZ.rglob("*")):
        rel = ruta.relative_to(RAIZ)
        partes = set(rel.parts)
        if not ruta.is_file() or partes & EXCLUIR_DIRS - ({"data"} if ruta.name in CONSERVAR_VACIOS else set()):
            continue
        if ruta.name in EXCLUIR_ARCHIVOS or ruta.suffix == ".pyc":
            continue
        clave = rel.as_posix()
        if sin_cuentas and clave in SOLO_SERVIDOR:
            continue
        if ruta.suffix.lower() in BINARIOS_EXT:
            binarios[clave] = base64.b64encode(ruta.read_bytes()).decode("ascii")
        else:
            texto[clave] = ruta.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return texto, binarios


def literal(obj) -> str:
    """JSON como literal de Python entre comillas simples (mismo formato del instalador original)."""
    js = json.dumps(obj, ensure_ascii=True)
    return "'" + js.replace("\\", "\\\\").replace("'", "\\'") + "'"


def generar(plantilla: str, texto: dict, binarios: dict) -> str:
    s = plantilla
    # las comprobaciones van sobre la plantilla: el contenido insertado incluye este mismo script
    necesita_base64 = "import base64" not in plantilla
    necesita_binarios = "BINARIOS.items()" not in plantilla
    nuevo = "ARCHIVOS = json.loads(" + literal(texto) + ")\nBINARIOS = json.loads(" + literal(binarios) + ")\n"
    viejo = '    print(f"{len(ARCHIVOS)} archivos creados en {DESTINO}")'
    if necesita_binarios and viejo not in plantilla:
        raise SystemExit("No encontré dónde agregar la escritura de archivos binarios.")
    s, n = re.subn(r"^ARCHIVOS = json\.loads\(.*\)\n(BINARIOS = json\.loads\(.*\)\n)?", lambda _m: nuevo, s,
                   count=1, flags=re.M)
    if n != 1:
        raise SystemExit("La plantilla no tiene la línea ARCHIVOS = json.loads(...).")
    if necesita_base64:
        s = s.replace("import json\n", "import base64\nimport json\n", 1)
    if necesita_binarios:
        s = s.replace(viejo, ESCRIBIR_BINARIOS, 1)
    return s


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    destino = Path(args[0])
    texto, binarios = recolectar("--sin-cuentas" in sys.argv)
    salida = generar(destino.read_text(encoding="utf-8"), texto, binarios)
    destino.write_text(salida, encoding="utf-8", newline="\n")
    print(f"{destino}: {len(texto)} archivos de texto + {len(binarios)} binarios, {len(salida) // 1024} KB")


if __name__ == "__main__":
    main()
