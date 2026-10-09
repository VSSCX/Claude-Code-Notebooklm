"""Cuentas por analista, historial de actividad y registro de errores."""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/cuentas.db")
os.environ.setdefault("VISORES_DIR", f"{_tmp}/visores")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app import registro, seguridad  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Actividad, Base, ErrorLog, ErrorOcurrencia, SesionWeb, Usuario  # noqa: E402

H = {"X-Requested-With": "od"}


@pytest.fixture()
def c():
    Base.metadata.create_all(engine)
    _limpiar()
    seguridad._fallos.clear() if hasattr(seguridad, "_fallos") else None
    with TestClient(app, client=("127.0.0.1", 50000)) as cl:
        yield cl
    _limpiar()


def _limpiar():
    with SessionLocal() as s:
        for m in (SesionWeb, ErrorOcurrencia, ErrorLog, Actividad, Usuario):
            s.execute(delete(m))
        s.commit()
    seguridad.olvidar_modo()


def _admin(c):
    r = c.post("/api/sesion/configuracion-inicial", json={"usuario": "vicente", "nombre": "Vicente S.", "clave": "Clave-segura1"}, headers=H)
    assert r.status_code == 200, r.text
    return r


def test_modo_abierto_sin_cuentas(c):
    assert c.get("/api/sesion").json()["modo"] == "abierto"
    assert c.get("/api/estado").status_code in (200, 404)        # sin cuentas no pide entrar


def test_primera_cuenta_y_exige_entrar(c):
    _admin(c)
    assert c.get("/api/sesion").json()["cuenta"]["rol"] == "admin"
    with TestClient(app, client=("127.0.0.1", 50000)) as otro:      # otro navegador, sin cookie
        e = otro.get("/api/sesion").json()
        assert e["modo"] == "cuentas" and not e["abierta"]
        r = otro.get("/api/admin/resumen")
        assert r.status_code == 401
        assert r.headers["x-request-id"]


def test_clave_debil_y_segunda_configuracion(c):
    r = c.post("/api/sesion/configuracion-inicial", json={"usuario": "ana", "clave": "corta"}, headers=H)
    assert r.status_code == 422
    _admin(c)
    r = c.post("/api/sesion/configuracion-inicial", json={"usuario": "otra", "clave": "Clave-segura2"}, headers=H)
    assert r.status_code == 409


def test_login_bloqueo_y_cookie(c):
    _admin(c)
    c.delete("/api/sesion", headers=H)
    for i in range(5):
        r = c.post("/api/sesion", json={"usuario": "vicente", "clave": "mala"}, headers=H)
        assert r.status_code in (401, 429)
    r = c.post("/api/sesion", json={"usuario": "vicente", "clave": "Clave-segura1"}, headers=H)
    assert r.status_code == 429                                 # bloqueado aunque la clave sea buena
    seguridad.limpiar_fallos("vicente", "testclient")
    seguridad.limpiar_fallos("vicente", "127.0.0.1")


def test_login_ok_cookie_httponly(c):
    _admin(c)
    c.delete("/api/sesion", headers=H)
    r = c.post("/api/sesion", json={"usuario": "VICENTE", "clave": "Clave-segura1"}, headers=H)
    assert r.status_code == 200
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc
    with SessionLocal() as s:                                   # nunca se guarda el token en claro
        tokens = [x.token_hash for x in s.scalars(select(SesionWeb))]
    assert r.cookies.get(seguridad.COOKIE) not in tokens


def test_csrf_exige_cabecera(c):
    _admin(c)
    r = c.put("/api/config/x", json={"valor": "1"})
    assert r.status_code == 403
    assert c.put("/api/config/x", json={"valor": "1"}, headers=H).status_code != 403


def test_sesion_caduca_por_inactividad(c):
    from datetime import timedelta
    _admin(c)
    with SessionLocal() as s:
        se = s.scalars(select(SesionWeb)).first()
        se.vista = se.vista - timedelta(hours=seguridad.settings.sesion_horas + 1)
        s.commit()
    assert c.get("/api/admin/resumen").status_code == 401


def test_analista_no_entra_a_admin_y_admin_gestiona(c):
    _admin(c)
    r = c.post("/api/admin/usuarios", json={"usuario": "andrea", "nombre": "Andrea R.", "rol": "analista"}, headers=H)
    assert r.status_code == 201
    temp = r.json()["clave_temporal"]
    uid = r.json()["id"]
    with TestClient(app, client=("127.0.0.1", 50000)) as a:
        assert a.post("/api/sesion", json={"usuario": "andrea", "clave": temp}, headers=H).status_code == 200
        # debe cambiar la clave antes de seguir
        assert a.get("/api/admin/resumen").status_code == 403
        r = a.post("/api/sesion/clave", json={"actual": temp, "nueva": "Nueva-clave9"}, headers=H)
        assert r.status_code == 200, r.text
        assert a.get("/api/admin/resumen").status_code == 403         # ahora por rol
        assert a.get("/api/mi/actividad").status_code == 200
    assert c.put(f"/api/admin/usuarios/{uid}", json={"activo": False}, headers=H).status_code == 200
    with TestClient(app, client=("127.0.0.1", 50000)) as a:
        assert a.post("/api/sesion", json={"usuario": "andrea", "clave": "Nueva-clave9"}, headers=H).status_code == 401


def test_siempre_queda_un_admin(c):
    _admin(c)
    uid = c.get("/api/admin/usuarios").json()["filas"][0]["id"]
    assert c.put(f"/api/admin/usuarios/{uid}", json={"activo": False}, headers=H).status_code == 409
    assert c.put(f"/api/admin/usuarios/{uid}", json={"rol": "analista"}, headers=H).status_code == 409


def test_actividad_por_analista(c):
    _admin(c)
    c.put("/api/config/prueba", json={"valor": "1"}, headers=H)
    filas = c.get("/api/admin/actividad?usuario=vicente").json()
    assert filas["total"] >= 1
    assert all(f["usuario"] == "vicente" for f in filas["filas"])
    assert any(f["categoria"] == "cuenta" for f in filas["filas"])
    csv = c.get("/api/admin/actividad.csv")
    assert csv.status_code == 200 and "Usuario" in csv.text
    mia = c.get("/api/mi/actividad").json()
    assert mia["usuario"] == "vicente" and mia["total"] >= 1


def test_errores_se_agrupan_y_se_reabren(c):
    _admin(c)
    for _ in range(3):
        r = c.post("/api/log/cliente", json={"mensaje": "TypeError: x is undefined", "pila": "at pintar (app.js:10:5)", "url": "/", "vista": "pedidos"}, headers=H)
        assert r.json()["ok"]
    lista = c.get("/api/admin/errores").json()["filas"]
    assert len(lista) == 1 and lista[0]["cuenta"] == 3 and lista[0]["origen"] == "navegador"
    eid = lista[0]["id"]
    d = c.get(f"/api/admin/errores/{eid}").json()
    assert len(d["ocurrencias"]) == 3 and d["ocurrencias"][0]["usuario"] == "vicente"
    assert c.put(f"/api/admin/errores/{eid}", json={"estado": "resuelto", "nota": "arreglado"}, headers=H).json()["estado"] == "resuelto"
    c.post("/api/log/cliente", json={"mensaje": "TypeError: x is undefined", "pila": "at pintar (app.js:10:5)", "url": "/"}, headers=H)
    assert c.get(f"/api/admin/errores/{eid}").json()["estado"] in ("nuevo", "visto")


def test_error_interno_lleva_codigo_y_queda_registrado(c):
    @app.get("/api/_prueba_error")
    def _boom():
        raise RuntimeError("falla de prueba")
    with TestClient(app, client=("127.0.0.1", 50000), raise_server_exceptions=False) as cl:
        r = cl.get("/api/_prueba_error")
    assert r.status_code == 500
    rid = r.headers["x-request-id"]
    assert rid in r.json()["detail"]
    with SessionLocal() as s:
        oc = s.scalars(select(ErrorOcurrencia).where(ErrorOcurrencia.request_id == rid)).first()
        assert oc is not None
        assert "falla de prueba" in s.get(ErrorLog, oc.error_id).mensaje


def test_no_se_guardan_secretos_en_el_contexto(c):
    registro.registrar_error("servidor", "x", contexto={"clave": "secreta", "ok": 1})
    with SessionLocal() as s:
        oc = s.scalars(select(ErrorOcurrencia)).first()
        assert "secreta" not in oc.contexto and '"ok"' in oc.contexto


def test_servidor_y_purga(c):
    _admin(c)
    d = c.get("/api/admin/servidor").json()
    assert d["autenticacion"] == "cuentas" and "python" in d
    assert c.post("/api/admin/purgar", headers=H).status_code == 200


def test_ping_publico_para_monitoreo(c):
    _admin(c)
    with TestClient(app, client=("10.0.0.9", 50000)) as otro:
        r = otro.get("/api/ping")
        assert r.status_code == 200 and r.json() == {"ok": True}


def test_usuarios_iniciales_del_env_se_crean_una_vez_y_con_clave_temporal(c):
    from app.config import settings
    object.__setattr__(settings, "usuarios_iniciales", "EvelynP:Elux1234;JuanS:Elux1234:Juan S.;malo:corta;EvelynP:Otra12345")
    try:
        with SessionLocal() as s:
            assert seguridad.crear_usuarios_iniciales(s) == ["evelynp", "juans"]       # la clave corta y el repetido se ignoran
            assert seguridad.crear_usuarios_iniciales(s) == []                          # idempotente
            u = s.scalar(select(Usuario).where(Usuario.usuario == "juans"))
            assert u.nombre == "Juan S." and u.rol == "analista" and u.debe_cambiar_clave
            assert seguridad.verificar("Elux1234", u.clave_hash)
    finally:
        object.__setattr__(settings, "usuarios_iniciales", "")


def test_sin_cuentas_no_se_pregunta_el_nombre_y_se_usa_el_usuario_de_windows(c, monkeypatch):
    from app import usuarios
    monkeypatch.setattr(usuarios, "usuario_del_sistema", lambda: "sotovic")
    e = c.get("/api/sesion").json()
    assert e["modo"] == "abierto" and e["usuario"] == "sotovic" and not e["requiere_clave"]
    assert c.get("/api/sesion", headers={"X-Usuario": "Ana"}).json()["usuario"] == "Ana"     # si el navegador manda uno, manda ese
    assert usuarios.entrar("", "")                                                            # y una sesión sin nombre ya no da error
