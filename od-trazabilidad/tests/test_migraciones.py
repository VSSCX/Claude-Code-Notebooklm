"""Las migraciones no pueden perder datos, y la herramienta de recuperación devuelve lo que se perdió."""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _alembic(base: Path, destino: str):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{base.as_posix()}", "PYTHONPATH": str(RAIZ)}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", destino], cwd=RAIZ, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def _entrega(con, pedido_id, numero, grupo="", camion_ref="", suministro=1, lineas=(), pasos=(), eventos=()):
    cols = {r[1] for r in con.execute("pragma table_info(entregas)")}
    vals = {"entrega": numero, "pedido_id": pedido_id, "grupo": grupo, "tipo": "Stock", "cita_numero": "", "cita_hora": "",
            "vehiculo": "Rampla 53", "carga": "MIX", "un": "MDA", "region": "RM", "factura": "", "obs": "", "anulada": 0,
            "reprogramaciones": 0, "camion_ref": camion_ref, "suministro": suministro, "creado": "2026-01-01", "actualizado": "2026-01-01"}
    use = [k for k in vals if k in cols]
    cur = con.execute(f"insert into entregas({','.join(use)}) values({','.join('?' * len(use))})", [vals[k] for k in use])
    eid = cur.lastrowid
    con.executemany("insert into lineas_entrega(entrega_id, sku, qty) values (?, ?, ?)", [(eid, s, q) for s, q in lineas])
    con.executemany("insert into pasos_entrega(entrega_id, paso, ok, at) values (?, ?, 1, '2026-01-01')", [(eid, p) for p in pasos])
    con.executemany("insert into eventos(entrega_id, at, origen, texto) values (?, '2026-01-01', 'web', ?)", [(eid, t) for t in eventos])
    return eid


def _pedido(con, numero):
    return con.execute("insert into pedidos(pedido, oc, cliente, canal, obs, creado, actualizado) values (?, '', 'X', '', '', '2026-01-01', '2026-01-01')",
                       (numero,)).lastrowid


def test_la_migracion_a_la_ultima_version_conserva_lineas_pasos_e_historial(tmp_path):
    base = tmp_path / "t.db"
    _alembic(base, "0009")
    con = sqlite3.connect(base)
    pid = _pedido(con, "1")
    _entrega(con, pid, "870", grupo="555", lineas=[("900", 10), ("901", 5)], pasos=["solicitada", "confirmada"], eventos=["Entrega creada"])
    con.commit()
    con.close()
    _alembic(base, "head")
    con = sqlite3.connect(base)
    assert con.execute("select count(*) from lineas_entrega").fetchone()[0] == 2
    assert con.execute("select count(*) from pasos_entrega").fetchone()[0] == 2
    assert con.execute("select count(*) from eventos").fetchone()[0] == 1
    assert con.execute("select grupo, categoria from entregas").fetchone() == ("555", "")
    # antes de cambiar la estructura queda una copia aparte
    assert list(tmp_path.glob("premigracion-0009-*.db"))


def _herramienta():
    spec = importlib.util.spec_from_file_location("recuperar_entregas", RAIZ / "herramientas" / "recuperar_entregas.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_recuperar_entregas_desde_un_respaldo_y_desde_el_cubicaje(tmp_path):
    base, resp = tmp_path / "data" / "t.db", tmp_path / "data" / "respaldos" / "trazabilidad-2026-10-20.db"
    base.parent.mkdir(parents=True)
    resp.parent.mkdir(parents=True)
    _alembic(base, "head")
    con = sqlite3.connect(base)
    # 1) entrega vieja, con detalle en el respaldo
    p1 = _pedido(con, "100")
    _entrega(con, p1, "8701", grupo="9001", pasos=[], lineas=[])
    # 2) camión compartido más nuevo que el respaldo: se arma con el cubicaje conjunto
    p2 = _pedido(con, "200")
    _entrega(con, p2, "8702", camion_ref="JABC-2")
    con.execute("insert into config(clave, valor) values ('conjunto:JABC', ?)", (json.dumps({"filas": [
        {"pedido": "200", "camion": 2, "sku": "A", "unidades": 7}, {"pedido": "200", "camion": 2, "sku": "B", "unidades": 3},
        {"pedido": "999", "camion": 2, "sku": "A", "unidades": 50}, {"pedido": "200", "camion": 1, "sku": "A", "unidades": 9}]}),))
    # 3) un pedido simple: dos entregas, dos camiones, sin detalle → por orden
    p3 = _pedido(con, "300")
    _entrega(con, p3, "8703")
    _entrega(con, p3, "8704")
    con.execute("insert into config(clave, valor) values ('cubicaje:300', ?)", (json.dumps({"filas": [
        {"camion": 1, "sku": "X", "unidades": 4}, {"camion": 2, "sku": "Y", "unidades": 6}]}),))
    con.commit()
    con.close()
    # el respaldo es la base de antes de perder el detalle
    con = sqlite3.connect(resp)
    con.close()
    import shutil
    shutil.copy2(base, resp)
    con = sqlite3.connect(resp)
    eid = con.execute("select id from entregas where entrega = '8701'").fetchone()[0]
    con.executemany("insert into lineas_entrega(entrega_id, sku, qty) values (?, ?, ?)", [(eid, "900", 10), (eid, "901", 5)])
    con.execute("insert into pasos_entrega(entrega_id, paso, ok, at) values (?, 'solicitada', 1, '2026-01-01')", (eid,))
    con.execute("insert into eventos(entrega_id, at, origen, texto) values (?, '2026-01-01', 'web', 'Entrega creada')", (eid,))
    con.commit()
    con.close()

    m = _herramienta()
    seco = m.recuperar(base, [resp], aplicar=False, reconstruir=True)
    assert set(seco["recuperadas"]) == {"8701", "8702", "8703", "8704"} and not seco["sin_resolver"]
    con = sqlite3.connect(base)
    assert con.execute("select count(*) from lineas_entrega").fetchone()[0] == 0          # sin --aplicar no se toca nada
    con.close()

    r = m.recuperar(base, [resp], aplicar=True, reconstruir=True)
    assert r["copia"] and Path(r["copia"]).exists()
    con = sqlite3.connect(base)
    lin = {(e, s): q for e, s, q in con.execute("select e.entrega, l.sku, l.qty from lineas_entrega l join entregas e on e.id = l.entrega_id")}
    assert lin == {("8701", "900"): 10, ("8701", "901"): 5, ("8702", "A"): 7, ("8702", "B"): 3, ("8703", "X"): 4, ("8704", "Y"): 6}
    assert con.execute("select count(*) from pasos_entrega").fetchone()[0] == 1               # los pasos solo vuelven si estaban en un respaldo
    assert con.execute("select count(*) from eventos where texto like 'Detalle de la entrega recuperado%'").fetchone()[0] == 4
    con.close()
    # volver a correrla no duplica nada
    assert m.recuperar(base, [resp], aplicar=True, reconstruir=True)["sin_detalle"] == 0


def test_sin_reconstruir_las_entregas_nuevas_quedan_avisadas(tmp_path):
    base = tmp_path / "t.db"
    _alembic(base, "head")
    con = sqlite3.connect(base)
    _entrega(con, _pedido(con, "1"), "8801")
    con.commit()
    con.close()
    r = _herramienta().recuperar(base, [], aplicar=True)
    assert r["sin_resolver"] == ["8801"] and r["recuperadas"] == {} and not r["copia"]
