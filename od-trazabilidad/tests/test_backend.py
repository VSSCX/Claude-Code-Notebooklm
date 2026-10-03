"""Revisión del backend: estado rápido e idéntico, motor SQL único, lecturas de red sin
bloqueos, reserva atómica de acciones y clave de acceso."""
import os
import tempfile
import threading
import time
from types import SimpleNamespace

import pytest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test_backend.db")
os.environ.setdefault("VISORES_DIR", f"{_tmp}/visores")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app import domain, usuarios  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.integrations import acciones, base_medidas, bases, maestra  # noqa: E402
from app.models import (Archivo, Base, Config, Entrega, Evento, LineaEntrega, LineaPedido,  # noqa: E402
                        PasoEntrega, Pedido, ahora)


@pytest.fixture()
def datos():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        for i in range(6):
            p = Pedido(pedido=f"40051{i:05d}", cliente="RIPLEY", oc=f"OC{i}", obs="ñandú" if i == 0 else "")
            p.lineas = [LineaPedido(sku=f"9000{j}", descripcion="" if j % 2 else f"Prod {j}", qty=10 + j,
                                    externa=j) for j in range(4)]
            for k in range(2):
                e = Entrega(entrega=f"87{i}{k}", grupo=f"G{i}", vehiculo="Rampla 53")
                e.lineas = [LineaEntrega(sku=f"9000{j}", qty=3 + j) for j in range(3)]
                e.pasos = [PasoEntrega(paso="solicitada", ok=True), PasoEntrega(paso="sap", ok=False)]
                # más eventos que el máximo: solo deben salir los últimos
                e.eventos = [Evento(texto=f"evento {n}", origen="web", at=ahora().replace(microsecond=n * 1000))
                             for n in range(domain.LOG_MAX + 15)]
                p.entregas.append(e)
            s.add(p)
        s.flush()
        s.add(Archivo(pedido_id=s.scalar(select(Pedido.id).limit(1)), tipo="pdf", nombre="a.pdf", archivo="x.pdf"))
        s.add(Archivo(pedido_id=None, tipo="adjunto", nombre="b.pdf", archivo="y.pdf"))
        s.add(Config(clave="k", valor='{"a": 1}'))
        s.commit()
    yield


def _estado_orm(s):
    """La versión anterior de domain.estado (objetos del ORM): referencia para comparar."""
    peds = s.scalars(select(Pedido).options(selectinload(Pedido.lineas))).all()
    ents = s.scalars(select(Entrega).options(
        selectinload(Entrega.lineas), selectinload(Entrega.pasos),
        selectinload(Entrega.eventos), selectinload(Entrega.pedido_ref))).all()
    desc = maestra.descripciones()
    import json
    return {
        "pedidos": [domain.pedido_doc(p, desc) for p in peds],
        "entregas": [domain.entrega_doc(e) for e in ents],
        "config": {c.clave: json.loads(c.valor or "{}") for c in s.scalars(select(Config)).all()},
        "archivos": [domain.archivo_doc(a, p.pedido if p else "")
                     for a, p in s.execute(select(Archivo, Pedido).join(Pedido, isouter=True)
                                           .order_by(Archivo.at.desc())).all()],
        "version": domain.version(s),
    }


def test_estado_igual_al_de_objetos(datos):
    with SessionLocal() as s:
        nuevo, viejo = domain.estado(s), _estado_orm(s)
    assert nuevo["pedidos"] == viejo["pedidos"]
    assert nuevo["config"] == viejo["config"] and nuevo["version"] == viejo["version"]
    assert nuevo["archivos"] == viejo["archivos"]
    assert len(nuevo["entregas"]) == len(viejo["entregas"]) == 12
    for n, v in zip(nuevo["entregas"], viejo["entregas"]):
        assert n == v


def test_estado_solo_trae_el_historial_reciente(datos):
    with SessionLocal() as s:
        e = domain.estado(s)["entregas"][0]
    assert len(e["log"]) == domain.LOG_MAX
    assert e["log"][0]["txt"] == f"evento {domain.LOG_MAX + 14}"     # lo más nuevo primero


def test_estado_vacio():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        e = domain.estado(s)
    assert e["pedidos"] == [] and e["entregas"] == [] and e["archivos"] == []


# ---------- motor SQL ----------
def test_un_solo_motor_para_las_consultas(monkeypatch):
    monkeypatch.setattr(bases, "_guardada", {"url": "sqlite://"})
    bases._soltar_motor()
    a, b = bases.motor_bases(), bases.motor_bases()
    assert a is b
    bases.usar_conexion({"url": "sqlite:///otro.db"})          # cambiar la conexión rehace el motor
    assert bases.motor_bases() is not a
    bases.usar_conexion({})


# ---------- lecturas de red ----------
class _RutaCaida:
    llamadas = 0

    def __init__(self, *_):
        pass

    def stat(self):
        _RutaCaida.llamadas += 1
        raise OSError("la red no responde")


@pytest.mark.parametrize("modulo, config, funcion", [
    (maestra, "maestra_homologacion", "descripciones"),
    (base_medidas, "base_medidas", "medidas"),
])
def test_red_caida_no_se_reintenta_en_cada_peticion(monkeypatch, modulo, config, funcion):
    monkeypatch.setattr(modulo, "settings", SimpleNamespace(**{config: r"\\servidor\x.xlsx"}))
    monkeypatch.setattr(modulo, "Path", _RutaCaida)
    monkeypatch.setitem(modulo._estado, "revisado", 0.0)
    monkeypatch.setitem(modulo._estado, "mtime", None)
    _RutaCaida.llamadas = 0
    for _ in range(5):
        getattr(modulo, funcion)()
    assert _RutaCaida.llamadas == 1


def test_red_lenta_no_bloquea_a_las_demas_peticiones(monkeypatch):
    monkeypatch.setattr(maestra, "settings", SimpleNamespace(maestra_homologacion="x.xlsx"))
    monkeypatch.setitem(maestra._estado, "revisado", 0.0)
    monkeypatch.setitem(maestra._estado, "datos", {"1": "algo"})
    suelta = threading.Event()

    class Lenta:
        def __init__(self, *_):
            pass

        def stat(self):
            suelta.wait(5)
            raise OSError("tarde")

    monkeypatch.setattr(maestra, "Path", Lenta)
    t = threading.Thread(target=maestra.descripciones)
    t.start()
    time.sleep(0.2)
    inicio = time.time()
    assert maestra.descripciones() == {"1": "algo"}              # no espera la red
    assert time.time() - inicio < 0.5
    suelta.set()
    t.join()


# ---------- acciones ----------
def test_una_sola_accion_a_la_vez_y_lista_acotada():
    soltar = threading.Event()
    empezo = threading.Event()

    def larga(_avance):
        empezo.set()
        soltar.wait(5)
        return "ok"

    primero = acciones.lanzar_python("t1", "Larga", [], larga)
    empezo.wait(2)
    with pytest.raises(RuntimeError, match="Ya hay una acción"):
        acciones.lanzar_python("t2", "Otra", [], lambda _a: None)
    soltar.set()
    for _ in range(100):
        if acciones.trabajo(primero["id"])["estado"] != "en_curso":
            break
        time.sleep(0.02)
    for _ in range(100):                                           # la reserva se libera al terminar
        if not acciones._ocupado[0]:
            break
        time.sleep(0.02)
    for i in range(acciones.MAX_TRABAJOS + 10):
        acciones.lanzar_python("t", f"n{i}", [], lambda _a: None)
        for _ in range(100):
            if not acciones._ocupado[0]:
                break
            time.sleep(0.01)
    assert len(acciones._trabajos) <= acciones.MAX_TRABAJOS


def test_dos_acciones_simultaneas_solo_deja_pasar_una():
    resultados, barrera = [], threading.Barrier(8)

    def intentar():
        barrera.wait()
        try:
            acciones.lanzar_python("p", "P", [], lambda _a: time.sleep(0.3))
            resultados.append("ok")
        except RuntimeError:
            resultados.append("ocupado")

    hilos = [threading.Thread(target=intentar) for _ in range(8)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert resultados.count("ok") == 1 and resultados.count("ocupado") == 7
    time.sleep(0.5)


# ---------- clave de acceso ----------
def test_con_clave_todo_queda_detras_de_la_sesion(monkeypatch, datos):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr(usuarios, "settings", SimpleNamespace(clave_acceso="secreta"))
    monkeypatch.setattr(usuarios, "_sesiones", set())
    c = TestClient(app)
    assert c.get("/api/estado").status_code == 401
    assert c.get("/archivos/1").status_code == 401                 # antes se podía abrir sin sesión
    assert c.get("/visor/visor_vivo.html").status_code == 401
    assert c.get("/").status_code == 200                           # la página carga para poder pedir la clave
    assert c.post("/api/sesion", json={"clave": "mala", "usuario": "Ana"}).status_code == 401
    assert c.post("/api/sesion", json={"clave": "secreta", "usuario": "Ana"}).status_code == 200
    assert c.get("/api/estado").status_code == 200
    assert c.get("/archivos/999").status_code == 404                # con sesión llega a la ruta


def test_sin_clave_nada_cambia(datos):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/estado").status_code == 200


# ---------- SAP: errores claros ----------
def test_accion_en_curso_responde_409_en_todos_los_endpoints_sap(monkeypatch, datos):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    with SessionLocal() as s:
        domain.guardar_config(s, "cubicaje:4005100000", {"filas": [{"camion": 1, "sku": "9000", "unidades": 5}]})
        s.commit()
    llamadas = [
        ("/api/sap/crear_entregas", {"pedido": "4005100000", "puesto": "PN01", "ensayo": True}),
        ("/api/sap/crear_grupo", {"entregas": ["8700"], "ensayo": True}),
        ("/api/sap/fecha_grupo", {"grupo": "123", "fecha": "01.10.2026", "ensayo": True}),
    ]
    acciones._ocupado[0] = True
    try:
        for ruta, cuerpo in llamadas:
            r = c.post(ruta, json=cuerpo)
            assert r.status_code == 409, (ruta, r.status_code, r.text)
            assert "Ya hay una acción" in r.json()["detail"]
    finally:
        acciones._ocupado[0] = False


def test_ajuste_de_carga_rechaza_nan_e_infinito(datos):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    with SessionLocal() as s:
        domain.guardar_config(s, "analisis:4005100000", {"posiciones": [{"sku": "9000"}], "ajustes": {}})
        s.commit()
    for malo in ("nan", "inf", "-1"):
        r = c.put("/api/analisis/4005100000/carga", json={"sku": "9000", "carga": malo})
        assert r.status_code == 422, (malo, r.text)


def test_entrega_creada_en_sap_se_informa_aunque_falle_el_registro(monkeypatch, datos):
    """Si no se puede guardar en la plataforma, no se aborta ni se pierde el número de la entrega."""
    import json
    from fastapi.testclient import TestClient
    from app.integrations import sap_crear
    from app.main import app
    c = TestClient(app)
    with SessionLocal() as s:
        domain.guardar_config(s, "cubicaje:4009999999", {"filas": [
            {"camion": 1, "sku": "9000", "unidades": 5}, {"camion": 2, "sku": "9000", "unidades": 7}]})
        s.commit()
    creadas = iter(["8800001", "8800002"])
    monkeypatch.setattr(sap_crear, "crear_entrega", lambda *a, **k: SimpleNamespace(
        ok=True, entrega=next(creadas), mensaje="", pasos=[], borradas=[], ajustadas=[], incidencias=[]))
    # el pedido no existe en la plataforma: guardar_entrega falla, como si la base no respondiera
    r = c.post("/api/sap/crear_entregas", json={"pedido": "4009999999", "puesto": "PN01", "ensayo": False,
                                                "confirmar": "4009999999"})
    assert r.status_code == 202
    for _ in range(100):
        t = c.get(f"/api/acciones/trabajos/{r.json()['id']}").json()
        if t["estado"] != "en_curso":
            break
        time.sleep(0.05)
    assert t["estado"] == "ok", t
    res = t["datos"]["resultados"]
    assert [x["entrega"] for x in res] == ["8800001", "8800002"]          # siguió con el segundo camión
    assert all("no se pudo registrar" in x["incidencias"][0] for x in res)
    time.sleep(0.2)
