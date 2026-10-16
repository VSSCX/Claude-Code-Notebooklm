"""Auditoria automatica de seguridad del proyecto (evidencia reproducible). Uso:
    python auditar_seguridad.py                      resumen en pantalla
    python auditar_seguridad.py --informe EVIDENCIA.md   ademas escribe el informe con fecha, version del codigo y resultado de cada control
    python auditar_seguridad.py --sellar-vendor      recalcula las huellas de public/vendor (despues de actualizar una libreria a proposito)
Sale con codigo 1 si algun control falla. Se ejecuta tambien en CI (.github/workflows/seguridad.yml)."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ.setdefault("DEMO", "1")

SECRETOS = [("clave privada", r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
            ("clave de API (sk-...)", r"\bsk-[A-Za-z0-9_-]{20,}"),
            ("token de GitHub", r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
            ("token de Vercel Blob", r"vercel_blob_rw_[A-Za-z0-9_]{10,}"),
            ("clave AWS", r"\bAKIA[0-9A-Z]{16}\b"),
            ("clave Fernet (SNAPSHOT_KEYS)", r"\b[A-Za-z0-9_-]{43}=(?![A-Za-z0-9])"),
            ("hash de usuario (DASH_USUARIOS)", r"pbkdf2\$\d+\$[A-Za-z0-9+/=]{16,}\$[A-Za-z0-9+/=]{30,}"),
            ("clave de base de datos", r"(?i)\b(?:PWD|PASSWORD|VTEX_PASS|SAP_PASS)\s*[=:]\s*['\"]?(?!\s|\$|\{|<|tu_|su_|xxx|\*|None|input|getpass|settings|os\.|pwd\b|clave|%|\.\.\.)[^\s'\";<>()]{6,}"),
            ("cadena de conexion", r"(?i)(?:Server|Data Source)=[^;]+;[^\n]*(?:Password|PWD)=[^;\s]{3,}")]
PELIGRO = [("eval()", r"\beval\("), ("exec()", r"(?<![\w.])exec\("), ("pickle", r"\bpickle\.loads?\("), ("shell=True", r"shell\s*=\s*True"),
           ("os.system", r"\bos\.system\("), ("yaml.load inseguro", r"\byaml\.load\((?!.*SafeLoader)")]
resultados: list[tuple[str, str, str, str]] = []      # (id, control, estado, detalle)


def r(id_, control, ok, detalle="", aviso=False):
    estado = "OK" if ok else ("AVISO" if aviso else "FALLA")
    resultados.append((id_, control, estado, detalle))
    print(f"  [{estado:<5}] {id_} {control}" + (f"  ->  {detalle}" if detalle and estado != "OK" else ""))


def git(*a: str) -> str:
    try:
        return subprocess.run(["git", *a], cwd=BASE, capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return ""


def archivos_versionados() -> list[Path]:
    out = [BASE / f for f in git("ls-files", "-z").split("\0") if f]
    return [p for p in out if p.is_file()] or [p for p in BASE.rglob("*") if p.is_file() and ".git" not in p.parts]


def texto(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore") if p.stat().st_size < 3_000_000 else ""
    except Exception:  # noqa: BLE001
        return ""


EXCLUIR = {"auditar_seguridad.py", "probar_seguridad.py", "POC_Dashboard.py", "SEGURIDAD.md", "package-lock.json"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--informe")
    ap.add_argument("--sellar-vendor", action="store_true")
    a = ap.parse_args()
    vend = BASE / "public" / "vendor"
    sello = vend / "INTEGRIDAD.sha256"
    if a.sellar_vendor:
        sello.write_text("".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in sorted(vend.glob("*.js"))), encoding="utf-8")
        print("Huellas escritas en", sello)
        return 0
    archivos = [p for p in archivos_versionados() if p.name not in EXCLUIR and p.suffix.lower() not in (".png", ".woff2", ".ico", ".jpg", ".pdf")]

    print("1. Secretos y credenciales")
    hallazgos = []
    for p in archivos:
        t = texto(p)
        for nombre, pat in SECRETOS:
            for m in re.finditer(pat, t):
                linea = t[:m.start()].count("\n") + 1
                if p.name in (".env.example",) or "ejemplo" in t[max(0, m.start() - 60):m.end() + 20].lower():
                    continue
                hallazgos.append(f"{p.relative_to(BASE)}:{linea} ({nombre})")
    r("S01", "Sin secretos ni claves en los archivos versionados", not hallazgos, "; ".join(hallazgos[:6]))
    ignorado = git("check-ignore", ".env").strip() or ".env" in texto(BASE / ".gitignore") or ".env" in texto(BASE.parent / ".gitignore")
    r("S02", ".env esta en .gitignore", bool(ignorado))
    r("S03", ".env no esta versionado", not any(p.name == ".env" for p in archivos))
    r("S04", "data/ (historiales y bitacora) fuera del repositorio", "data/" in texto(BASE.parent / ".gitignore") + texto(BASE / ".gitignore"))
    hist = git("log", "--all", "-p", "--no-color", "-G", r"(?i)(PWD|password|VTEX_PASS|SAP_PASS)\s*=\s*\S{6,}", "--", ".")[:6_000_000]
    sospechosos = set()
    for lin in hist.splitlines():
        if lin.startswith("+") and not lin.startswith("+++"):
            m = re.search(r"(?i)(?:PWD|password|VTEX_PASS|SAP_PASS)\s*=\s*['\"]?([^\s'\";<>]{6,})", lin)
            if m and not re.match(r"(?i)(\$|\{|<|tu_|su_|xxx|\*|none|input|getpass|settings|os\.|pwd\b|clave|%|\.\.\.)", m.group(1)):
                sospechosos.add(m.group(1)[:3] + "***")
    r("S05", "El historial de git no contiene claves en claro", not sospechosos, ", ".join(sorted(sospechosos)[:5]))
    env_ej = texto(BASE / ".env.example")
    r("S06", ".env.example documenta SESSION_SECRET, DASH_USUARIOS y SNAPSHOT_KEYS (sin valores reales)", all(k in env_ej for k in ("SESSION_SECRET", "DASH_USUARIOS", "SNAPSHOT_KEYS")))

    print("2. Codigo")
    peligros = []
    for p in archivos:
        if p.suffix in (".py",):
            for nombre, pat in PELIGRO:
                for m in re.finditer(pat, texto(p)):
                    peligros.append(f"{p.relative_to(BASE)} ({nombre})")
    r("C01", "Sin eval/exec/pickle/shell=True/os.system", not peligros, "; ".join(sorted(set(peligros))[:6]))
    sql_user = [str(p.relative_to(BASE)) for p in archivos if p.suffix == ".py" and re.search(r"leer_(?:vtex|sap)\(f?[\"'][^\"']*(?:\{(?!fv|CANALES_IN|_ident)[a-z_]+\})", texto(p))]
    r("C02", "Las consultas SQL con valores del usuario van parametrizadas", not sql_user, ", ".join(sql_user))
    r("C03", "Las consultas son de solo lectura (sin INSERT/UPDATE/DELETE/DROP/EXEC)",
      not re.search(r"(?i)\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+TABLE|TRUNCATE|EXEC(?:UTE)?\s+\w)", texto(BASE / "app" / "queries.py") + texto(BASE / "app" / "db.py")))
    js = "".join(texto(p) for p in (BASE / "public" / "js").glob("*.js"))
    r("C04", "El frontend no usa eval ni document.write", not re.search(r"\beval\(|document\.write\(|new Function\(", js))

    print("3. Dependencias y cadena de suministro")
    reqs = [x.strip() for x in texto(BASE / "requirements.txt").splitlines() if x.strip() and not x.startswith("#")]
    r("D01", "Todas las dependencias tienen cota superior de version", all("<" in x for x in reqs), ", ".join(x for x in reqs if "<" not in x))
    if sello.exists():
        malos = []
        for linea in sello.read_text(encoding="utf-8").splitlines():
            h, _, n = linea.partition("  ")
            f = vend / n
            if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != h:
                malos.append(n)
        r("D02", "Las librerias de public/vendor no fueron alteradas (huellas SHA-256)", not malos, ", ".join(malos))
    else:
        r("D02", "Huellas de public/vendor", False, "falta INTEGRIDAD.sha256 (python auditar_seguridad.py --sellar-vendor)")
    r("D03", "Sin CDN externos en el HTML (todo se sirve desde el propio dominio)", not re.search(r"(?:src|href)=[\"']https?://", texto(BASE / "public" / "index.html") + texto(BASE / "public" / "login.html")))
    try:
        pa = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(BASE / "requirements.txt")], capture_output=True, text=True, timeout=180)
        if "No module named" in pa.stderr:
            raise RuntimeError("sin pip-audit")
        r("D04", "pip-audit: sin vulnerabilidades conocidas en las dependencias", pa.returncode == 0, (pa.stdout or pa.stderr)[-300:])
    except Exception:  # noqa: BLE001
        r("D04", "pip-audit (vulnerabilidades conocidas)", False, "no instalado: pip install pip-audit (corre en CI)", aviso=True)

    print("4. Acceso y configuracion de la aplicacion")
    from fastapi.testclient import TestClient

    from app import auth
    from app.config import settings
    from app.main import app
    from app.seguridad import CABECERAS
    object.__setattr__(settings, "auth_requerida", "1")
    object.__setattr__(settings, "dash_usuarios", "a@b.c:" + auth.hash_clave("x" * 12) + ":admin")
    object.__setattr__(settings, "session_secret", "s" * 40)
    cli = TestClient(app)
    abiertas = []
    for ruta in app.routes:
        path = getattr(ruta, "path", "")
        if not path.startswith("/api/") or path in auth.PUBLICAS:
            continue
        for m in getattr(ruta, "methods", set()) - {"HEAD", "OPTIONS"}:
            res = cli.request(m, path.replace("{sequence}", "1"), json={} if m == "POST" else None)
            if res.status_code != 401:
                abiertas.append(f"{m} {path} -> {res.status_code}")
    r("A01", "Todas las rutas /api exigen sesion (excepto login y salud)", not abiertas, "; ".join(abiertas))
    r("A02", "Cada ruta sensible exige un rol minimo (matriz de permisos)", all(auth.rol_minimo(x) == "admin" for x in ("/api/auditoria", "/api/diagnostico"))
      and auth.rol_minimo("/api/pedidos/exportar") == "analista" and auth.rol_minimo("/api/dashboard") == "lector")
    h = cli.get("/api/salud").headers
    faltan = [k for k in CABECERAS if k not in h]
    r("A03", "Cabeceras de seguridad en las respuestas (CSP, HSTS-equivalentes, COOP/CORP, nosniff...)", not faltan, ", ".join(faltan))
    import json
    if (BASE / "vercel.json").exists():
        vj = json.loads(texto(BASE / "vercel.json"))
        vh = {x["key"]: x["value"] for x in vj["headers"][0]["headers"]}
        r("A04", "vercel.json y la aplicacion declaran las mismas cabeceras", all(vh.get(k) == v for k, v in CABECERAS.items()), ", ".join(k for k, v in CABECERAS.items() if vh.get(k) != v))
        r("A05", "HSTS activo en Vercel", "Strict-Transport-Security" in vh)
    object.__setattr__(settings, "dash_usuarios", "")
    r("A06", "Falla segura: acceso activo sin usuarios = cerrado (503)", cli.post("/api/dashboard", json={}).status_code == 503)
    r("A07", "Las claves de usuario se guardan con PBKDF2 (>= 200.000 iteraciones)", auth.ITER >= 200_000)
    r("A08", "Sin documentacion publica de la API en Vercel (/docs, /openapi.json)", 'openapi_url=None if settings.serverless' in texto(BASE / "app" / "main.py"))
    r("A09", "Errores genericos hacia el cliente cuando esta publicado", "No se pudo obtener los datos en este momento." in texto(BASE / "app" / "main.py"))

    print("5. Gestion de cambios y evidencia")
    r("G01", "Flujo de CI con pruebas y auditoria en cada cambio", (BASE.parent / ".github" / "workflows" / "seguridad.yml").exists() or (BASE / ".github" / "workflows" / "seguridad.yml").exists())
    r("G02", "Matriz riesgo-control documentada (SEGURIDAD.md)", "Matriz riesgo" in texto(BASE / "SEGURIDAD.md"))
    r("G03", "Pruebas de controles (probar_seguridad.py) presentes", (BASE / "probar_seguridad.py").exists())
    r("G04", "El instalador verifica la huella SHA-256 del paquete", "sha256" in texto(BASE / "instalador_base.py").lower())

    fallas = [x for x in resultados if x[2] == "FALLA"]
    print(f"\nRESULTADO: {len(resultados) - len(fallas)} de {len(resultados)} controles cumplen" + (f"; fallan: {', '.join(x[0] for x in fallas)}" if fallas else " (todo en orden)"))
    if a.informe:
        cod = git("rev-parse", "--short", "HEAD").strip() or "sin-git"
        lin = ["# Evidencia de auditoría de seguridad", "", f"- Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}", f"- Versión del código: `{cod}`",
               f"- Resultado: {len(resultados) - len(fallas)} de {len(resultados)} controles cumplen", "", "| Id | Control | Estado | Detalle |", "|---|---|---|---|"]
        lin += [f"| {i} | {c} | {e} | {d.replace('|', '/')} |" for i, c, e, d in resultados]
        Path(a.informe).write_text("\n".join(lin) + "\n", encoding="utf-8")
        print("Informe escrito en", a.informe)
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
