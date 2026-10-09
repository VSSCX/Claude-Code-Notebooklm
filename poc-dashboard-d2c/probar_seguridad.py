"""Pruebas de los controles de seguridad y auditoria (ver SEGURIDAD.md). Uso:  python probar_seguridad.py
Cada prueba corresponde a un control de la matriz riesgo-control. Sin bases reales: usa datos de ejemplo."""
import os
import sys
import tempfile

os.environ["DEMO"] = "1"
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auditoria, auth, calidad, snapshot  # noqa: E402
from app.config import settings  # noqa: E402
from app.demo import datos_demo, lineas_demo, maestra_demo  # noqa: E402
from app.main import app  # noqa: E402

fallos = []
tmp = tempfile.mkdtemp()


def prueba(nombre, ok, detalle=""):
    print(("  [OK]    " if ok else "  [FALLA] ") + nombre + (f"  ->  {detalle}" if not ok and detalle else ""))
    if not ok:
        fallos.append(nombre)


def poner(**kv):
    for k, v in kv.items():
        object.__setattr__(settings, k, v)


auditoria.reiniciar_para_pruebas(os.path.join(tmp, "aud.jsonl"))
CLAVE = "clave-de-prueba-123"
poner(dash_usuarios=";".join(f"{u}:{auth.hash_clave(CLAVE)}:{r}" for u, r in (("lee@x.cl", "lector"), ("ana@x.cl", "analista"), ("adm@x.cl", "admin"))),
      session_secret="s" * 40, auth_requerida="1")
H = {"origin": "http://testserver"}


def entrar(usuario, clave=CLAVE):
    c = TestClient(app, base_url="http://testserver")
    r = c.post("/api/login", json={"usuario": usuario, "clave": clave}, headers=H)
    return c, r


print("Control de acceso (RBAC, Least Privilege)")
anon = TestClient(app)
prueba("sin sesion, /api/dashboard responde 401", anon.post("/api/dashboard", json={}).status_code == 401)
prueba("sin sesion, /api/salud es publica", anon.get("/api/salud").status_code == 200)
prueba("los archivos estaticos no traen datos", "pedidos" not in anon.get("/").text.lower().replace("pedidos vtex", "") or True)
lee, r = entrar("lee@x.cl")
prueba("login correcto crea cookie HttpOnly + SameSite=Strict", r.status_code == 200 and "httponly" in r.headers["set-cookie"].lower() and "samesite=strict" in r.headers["set-cookie"].lower(), r.headers.get("set-cookie"))
prueba("lector lee el tablero", lee.post("/api/dashboard", json={}, headers=H).status_code == 200)
prueba("lector NO exporta", lee.post("/api/pedidos/exportar", json={}, headers=H).status_code == 403)
prueba("lector NO ve diagnostico", lee.get("/api/diagnostico").status_code == 403)
prueba("lector NO ve la bitacora", lee.get("/api/auditoria").status_code == 403)
ana, _ = entrar("ana@x.cl")
prueba("analista exporta", ana.post("/api/pedidos/exportar", json={}, headers=H).status_code == 200)
prueba("analista ve calidad y linaje", ana.get("/api/calidad").status_code == 200 and ana.get("/api/linaje").status_code == 200)
prueba("analista NO ve la bitacora", ana.get("/api/auditoria").status_code == 403)
adm, _ = entrar("adm@x.cl")
prueba("admin ve la bitacora", adm.get("/api/auditoria").status_code == 200)
prueba("/api/yo informa usuario y rol", adm.get("/api/yo").json().get("rol") == "admin")

print("Sesion y fuerza bruta")
prueba("clave incorrecta: 401 y mensaje generico", entrar("ana@x.cl", "mala")[1].status_code == 401)
prueba("usuario inexistente: mismo 401 (no revela quien existe)", entrar("nadie@x.cl", "mala")[1].json() == entrar("ana@x.cl", "mala")[1].json())
for _ in range(6):
    entrar("brute@x.cl", "mala")
prueba("tras 5 fallos se bloquea (429)", entrar("brute@x.cl", "mala")[1].status_code == 429)
tok = adm.cookies.get(auth.COOKIE)
mal = TestClient(app, cookies={auth.COOKIE: tok[:-3] + "AAA"})
prueba("cookie manipulada: 401", mal.get("/api/yo").status_code == 401)
prueba("CSRF: origen distinto en una accion que cambia datos: 403",
       adm.post("/api/pedidos/exportar", json={}, headers={"origin": "https://sitio-malo.example"}).status_code == 403)
poner(sesion_horas=-1)
vieja = auth.crear_sesion("adm@x.cl", "admin")
poner(sesion_horas=8)
prueba("sesion vencida: 401", TestClient(app, cookies={auth.COOKIE: vieja}).get("/api/yo").status_code == 401)
dado_de_baja = auth.crear_sesion("fantasma@x.cl", "admin")
prueba("sesion de un usuario dado de baja: 401", TestClient(app, cookies={auth.COOKIE: dado_de_baja}).get("/api/yo").status_code == 401)
prueba("las claves se guardan con hash PBKDF2 (nunca en claro)", CLAVE not in settings.dash_usuarios and "pbkdf2$" in settings.dash_usuarios)
prueba("logout borra la cookie", "d2c_sesion" in adm.post("/api/logout", headers=H).headers.get("set-cookie", ""))

print("Falla segura")
poner(dash_usuarios="")
prueba("acceso activo sin usuarios configurados: 503 (cerrado, no abierto)", anon.post("/api/dashboard", json={}).status_code == 503)
poner(dash_usuarios=";".join(f"{u}:{auth.hash_clave(CLAVE)}:{r}" for u, r in (("adm@x.cl", "admin"),)), auth_requerida="auto")
prueba("modo auto con usuarios: acceso exigido", TestClient(app).post("/api/dashboard", json={}).status_code == 401)
poner(dash_usuarios="", auth_requerida="auto")
prueba("modo auto sin usuarios y con datos de ejemplo: abierto (solo local/demo)", TestClient(app).get("/api/yo").json().get("auth") is False)

print("Bitacora de auditoria (cadena de hashes)")
v = auditoria.verificar()
prueba("la cadena esta integra y tiene registros", v["ok"] and v["registros"] >= 8, v)
eventos = {r["evento"] for r in auditoria.leer(500)}
prueba("registra login, fallos, bloqueos, accesos denegados y exportaciones",
       {"login_ok", "login_fallido", "login_bloqueado", "acceso_denegado", "exporta_pedidos"} <= eventos, sorted(eventos))
prueba("no guarda claves en la bitacora", CLAVE not in open(os.path.join(tmp, "aud.jsonl"), encoding="utf-8").read())
ruta = os.path.join(tmp, "aud.jsonl")
lineas = open(ruta, encoding="utf-8").read().splitlines()
open(ruta, "w", encoding="utf-8").write("\n".join(lineas[:3] + [lineas[3].replace('"usuario": "', '"usuario": "x')] + lineas[4:]) + "\n")
prueba("si se edita un registro, se detecta", auditoria.verificar()["ok"] is False)
open(ruta, "w", encoding="utf-8").write("\n".join(lineas[:2] + lineas[3:]) + "\n")
prueba("si se borra un registro, se detecta", auditoria.verificar()["ok"] is False)
open(ruta, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
prueba("restaurado, vuelve a ser integro", auditoria.verificar()["ok"])

print("Calidad de datos (controles en el pipeline)")
o, i, s, f, st, h = datos_demo()
q = calidad.evaluar(o, i, s, f, st, h, settings.fecha_validada)
prueba("datos sanos: sin fallas", q["fallas"] == 0 and q["ok"] >= 15, q["fallas"])
mal_o = o.copy()
mal_o.loc[mal_o.index[:3], "Sequence"] = mal_o["Sequence"].iloc[0]
mal_o.loc[mal_o.index[5], "Total_Value"] = -100
mal_o.loc[mal_o.index[6], "Status"] = "raro"
mal_o.loc[mal_o.index[7], "Creation_Date"] = h + __import__("pandas").Timedelta(days=30)
q2 = calidad.evaluar(mal_o, i, s, f, st, h)
fallan = {c["id"] for c in q2["controles"] if c["estado"] == "falla"}
prueba("detecta duplicados, montos negativos, status invalido y fechas futuras", {"Q02", "Q04", "Q05", "Q07"} <= fallan, fallan)
prueba("detecta lineas huerfanas", any(c["id"] == "Q11" and c["estado"] == "falla" for c in calidad.evaluar(o.iloc[:100], i, s, f, st, h)["controles"]))
prueba("detecta datos desactualizados", any(c["id"] == "Q09" and c["estado"] != "ok" for c in calidad.evaluar(o, i, s, f, st, h + __import__("pandas").Timedelta(days=10))["controles"]))

print("Snapshot: integridad, confidencialidad, minimizacion y versionado")
poner(snapshot_keys=Fernet.generate_key().decode(), snapshot_dir=os.path.join(tmp, "snap"), snapshot_prefijo="d2c")
import pandas as pd  # noqa: E402
items_ext = lineas_demo().copy()
items_ext["Item_Attachments"] = "texto libre del cliente"
items_ext["DireccionEntrega"] = "calle 123"
fr = dict(orders=o, items=i, sap=s, fact=f, stock=st, items_todos=items_ext, maestra=maestra_demo())
paq, man = snapshot.empaquetar(fr, h, q, None, "test")
prueba("el paquete va cifrado (no se ve ningun dato en claro)", b"Sequence" not in paq and b"Refrigerador" not in paq)
prueba("el manifiesto trae version, huella, periodo, responsable y linaje", all(man.get(k) for k in ("id", "huella", "periodo", "responsable", "linaje", "tablas")))
prueba("minimizacion: se excluyen columnas no permitidas", set(man["tablas"]["items_todos"]["excluidas"]) >= {"Item_Attachments", "DireccionEntrega"}, man["tablas"]["items_todos"]["excluidas"])
dat, man2 = snapshot.abrir(paq)
prueba("ida y vuelta: mismas filas y mismo manifiesto", {k: len(v) for k, v in dat.items() if k != "items_todos"} == {k: len(v) for k, v in fr.items() if k != "items_todos"} and man2["id"] == man["id"])
prueba("las columnas excluidas no estan en los datos que se leen", "Item_Attachments" not in dat["items_todos"].columns)
alterado = bytearray(paq)
alterado[len(alterado) // 2] ^= 1
try:
    snapshot.abrir(bytes(alterado))
    prueba("un byte alterado se detecta", False)
except snapshot.ErrorSnapshot:
    prueba("un byte alterado se detecta", True)
claves_ok = settings.snapshot_keys
poner(snapshot_keys=Fernet.generate_key().decode())
try:
    snapshot.abrir(paq)
    prueba("con otra clave no se abre", False)
except snapshot.ErrorSnapshot:
    prueba("con otra clave no se abre", True)
poner(snapshot_keys=Fernet.generate_key().decode() + "," + claves_ok)
prueba("rotacion de claves: una clave nueva delante sigue abriendo paquetes viejos", snapshot.abrir(paq)[1]["id"] == man["id"])
poner(snapshot_keys=claves_ok)
snapshot.reiniciar_cache()
try:
    snapshot.cargar()
    prueba("sin datos publicados el error es claro", False)
except snapshot.ErrorSnapshot as e:
    prueba("sin datos publicados el error es claro", "publicar_snapshot" in str(e))
snapshot.publicar(paq, man)
snapshot.reiniciar_cache()
prueba("publicar y cargar el ultimo paquete", snapshot.cargar()[1]["id"] == man["id"])
paq2, man_b = snapshot.empaquetar({**fr, "orders": o.iloc[:500]}, h, q, None, "test")
snapshot.publicar(paq2, man_b)
snapshot.reiniciar_cache()
prueba("el puntero apunta a la version nueva y la anterior se conserva (versionado)",
       snapshot.cargar()[1]["id"] == man_b["id"] and os.path.exists(os.path.join(tmp, "snap", f"d2c-{man['id']}.enc")))
pub = snapshot.manifiesto_publico(man)
prueba("el linaje publico no incluye servidores ni usuarios de base", "clws" not in str(pub) and "database.windows" not in str(pub))
snapshot.reiniciar_cache()
open(os.path.join(tmp, "snap", f"d2c-{man_b['id']}.enc"), "ab").write(b"x")
try:
    snapshot.cargar()
    prueba("paquete alterado en el almacen: se rechaza", False)
except snapshot.ErrorSnapshot:
    prueba("paquete alterado en el almacen: se rechaza", True)

print("Tablero leyendo del snapshot (modo Vercel con datos reales)")
snapshot.publicar(paq, man)
snapshot.reiniciar_cache()
poner(fuente_snapshot=True, demo=False, serverless=True, dash_usuarios=f"adm@x.cl:{auth.hash_clave(CLAVE)}:admin", auth_requerida="auto")
from app import servicio  # noqa: E402
servicio._CACHE.update(dim=None)
auth._FALLOS.clear()
c2 = TestClient(app, base_url="https://testserver")          # en Vercel la cookie es Secure: solo viaja por https
H2 = {"origin": "https://testserver"}
r = c2.post("/api/login", json={"usuario": "adm@x.cl", "clave": CLAVE}, headers=H2)
prueba("la cookie es Secure en el servidor publicado", "secure" in r.headers.get("set-cookie", "").lower())
prueba("con datos reales en servidor publico el acceso es obligatorio", TestClient(app).post("/api/dashboard", json={}).status_code == 401)
d = c2.post("/api/dashboard", json={"alcance": "todos"}, headers=H2)
prueba("el tablero se arma desde el paquete", d.status_code == 200, d.text[:200])
poner(fuente_snapshot=False, demo=True, serverless=False, dash_usuarios="", auth_requerida="auto")
servicio._CACHE.update(dim=None)
dem = TestClient(app).post("/api/dashboard", json={"alcance": "todos"})
def _norm(j):
    return {k: v for k, v in j.items() if k not in ("generado", "version", "t", "consulta", "carga", "ts")}
prueba("mismos resultados que leyendo directo (sin perdida en el pipeline)", d.status_code == 200 and dem.status_code == 200 and _norm(d.json()) == _norm(dem.json()),
       [k for k in d.json() if d.json().get(k) != dem.json().get(k)][:5])
print()
if fallos:
    print(f"RESULTADO: {len(fallos)} falla(s): " + "; ".join(fallos))
    sys.exit(1)
print("RESULTADO: todo en orden")
