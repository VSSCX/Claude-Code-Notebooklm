"""Recupera las líneas, los pasos y el historial de entregas que quedaron sin detalle (solo se ve el número y el grupo).

Pasó con la actualización que trae la migración 0010 de la versión del 22-oct (borraba esas filas al ampliar una columna). Esta
herramienta las vuelve a poner desde los respaldos de data\\respaldos. Si una entrega es más nueva que todos los respaldos, con
--reconstruir arma sus líneas desde el cubicaje guardado (se muestra qué se hizo para que lo revises).

Uso, desde la carpeta od-trazabilidad y con la plataforma CERRADA:
    .venv\\Scripts\\python herramientas\\recuperar_entregas.py                  (solo muestra qué se recuperaría)
    .venv\\Scripts\\python herramientas\\recuperar_entregas.py --aplicar        (lo hace, con copia previa de la base)
    .venv\\Scripts\\python herramientas\\recuperar_entregas.py --aplicar --reconstruir
    .venv\\Scripts\\python herramientas\\recuperar_entregas.py --respaldo data\\respaldos\\trazabilidad-2026-10-20.db
Solo usa la biblioteca estándar de Python; no modifica nada sin --aplicar.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _base_por_defecto() -> Path:
    try:
        sys.path.insert(0, str(RAIZ))
        from app.config import settings
        url = settings.database_url
        if url.startswith("sqlite"):
            p = Path(url.split("///")[-1])
            return p if p.is_absolute() else RAIZ / p
    except Exception:  # noqa: BLE001
        pass
    return RAIZ / "data" / "trazabilidad.db"


def _sin_lineas(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "select e.id, e.entrega, e.suministro, e.camion_ref, p.pedido from entregas e join pedidos p on p.id = e.pedido_id "
        "where e.anulada = 0 and not exists (select 1 from lineas_entrega l where l.entrega_id = e.id) order by e.entrega").fetchall()


def _del_respaldo(ruta: Path, faltan: dict[str, int]) -> dict[str, dict]:
    """Lo que el respaldo sabe de las entregas que faltan: {entrega: {lineas, pasos, eventos}}."""
    out: dict[str, dict] = {}
    try:
        con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return out
    con.row_factory = sqlite3.Row
    try:
        for r in con.execute("select id, entrega from entregas"):
            if r["entrega"] not in faltan:
                continue
            lineas = [(x["sku"], x["qty"]) for x in con.execute("select sku, qty from lineas_entrega where entrega_id = ?", (r["id"],))]
            if not lineas:
                continue
            out[r["entrega"]] = {
                "lineas": lineas,
                "pasos": [(x["paso"], x["ok"], x["at"]) for x in con.execute("select paso, ok, at from pasos_entrega where entrega_id = ?", (r["id"],))],
                "eventos": [(x["at"], x["origen"], x["texto"]) for x in con.execute("select at, origen, texto from eventos where entrega_id = ?", (r["id"],))]}
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


def _config(con: sqlite3.Connection, clave: str) -> dict | None:
    r = con.execute("select valor from config where clave = ?", (clave,)).fetchone()
    try:
        return json.loads(r["valor"]) if r else None
    except ValueError:
        return None


def _reconstruir(con: sqlite3.Connection, pendientes: list[sqlite3.Row]) -> dict[str, dict]:
    """Líneas de entregas sin respaldo, desde el cubicaje guardado. Dos casos seguros:
    · camión compartido (camion_ref «J1AB2C-3»): el cubicaje conjunto dice exactamente qué lleva ese camión de ese pedido;
    · entregas de un solo pedido: se asignan por orden (n.º de entrega ascendente = n.º de camión), solo si TODAS las entregas
      del pedido y suministro quedaron sin detalle y hay tantas como camiones."""
    out: dict[str, dict] = {}
    por_pedido: dict[tuple, list] = {}
    for e in pendientes:
        if e["camion_ref"] and "-" in e["camion_ref"]:
            cid, _, cam = e["camion_ref"].rpartition("-")
            doc = _config(con, f"conjunto:{cid}")
            if doc and cam.isdigit():
                suma: dict[str, int] = {}
                for f in doc.get("filas", []):
                    if str(f.get("pedido")) == e["pedido"] and int(f.get("camion", 0)) == int(cam):
                        suma[f["sku"]] = suma.get(f["sku"], 0) + int(f.get("unidades", 0))
                if suma:
                    out[e["entrega"]] = {"lineas": list(suma.items()), "origen": f"cubicaje conjunto {cid}, camión {cam}"}
                    continue
        por_pedido.setdefault((e["pedido"], e["suministro"] or 1), []).append(e)
    for (pedido, sm), es in por_pedido.items():
        total = con.execute("select count(*) from entregas e join pedidos p on p.id = e.pedido_id "
                            "where p.pedido = ? and e.anulada = 0 and coalesce(e.suministro, 1) = ?", (pedido, sm)).fetchone()[0]
        if total != len(es):
            continue                                              # alguna entrega conserva su detalle: el orden ya no es confiable
        actual = (_config(con, f"analisis:{pedido}") or {}).get("suministro", 1)
        doc = _config(con, f"cubicaje:{pedido}" if sm == actual else f"cubicaje:{pedido}:s{sm}")
        if not doc or doc.get("conjunto"):
            continue
        camiones = sorted({int(f["camion"]) for f in doc.get("filas", [])})
        if len(camiones) != len(es):
            continue
        for e, cam in zip(sorted(es, key=lambda x: x["entrega"]), camiones):
            suma: dict[str, int] = {}
            for f in doc["filas"]:
                if int(f["camion"]) == cam:
                    suma[f["sku"]] = suma.get(f["sku"], 0) + int(f.get("unidades", 0))
            out[e["entrega"]] = {"lineas": list(suma.items()), "origen": f"cubicaje de {pedido}, camión {cam} (por orden de entrega)"}
    return out


def recuperar(base: Path, respaldos: list[Path], aplicar: bool = False, reconstruir: bool = False) -> dict:
    con = sqlite3.connect(base)
    con.row_factory = sqlite3.Row
    con.execute("pragma foreign_keys = on")
    faltan_filas = _sin_lineas(con)
    faltan = {r["entrega"]: r["id"] for r in faltan_filas}
    hechas: dict[str, dict] = {}
    for ruta in respaldos:                                         # del respaldo más nuevo al más viejo
        for entrega, d in _del_respaldo(ruta, {k: v for k, v in faltan.items() if k not in hechas}).items():
            hechas[entrega] = {**d, "origen": f"respaldo {ruta.name}"}
    rec = {e: d for e, d in hechas.items()}
    sin = [r for r in faltan_filas if r["entrega"] not in rec]
    if reconstruir and sin:
        rec.update(_reconstruir(con, sin))
    sin_resolver = [r["entrega"] for r in faltan_filas if r["entrega"] not in rec]
    resultado = {"sin_detalle": len(faltan_filas), "recuperadas": {e: {"origen": d["origen"], "lineas": len(d["lineas"]),
                 "unidades": sum(q for _, q in d["lineas"])} for e, d in rec.items()}, "sin_resolver": sin_resolver, "copia": ""}
    if aplicar and rec:
        con.close()
        copia = base.parent / "respaldos" if base.parent.name == "data" else base.parent
        copia.mkdir(parents=True, exist_ok=True)
        destino = copia / f"antes-de-recuperar-{datetime.now():%Y%m%d-%H%M%S}.db"
        shutil.copy2(base, destino)
        resultado["copia"] = str(destino)
        con = sqlite3.connect(base)
        con.execute("pragma foreign_keys = on")
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with con:
            for entrega, d in rec.items():
                eid = faltan[entrega]
                con.executemany("insert or ignore into lineas_entrega(entrega_id, sku, qty) values (?, ?, ?)", [(eid, s, q) for s, q in d["lineas"]])
                con.executemany("insert or ignore into pasos_entrega(entrega_id, paso, ok, at) values (?, ?, ?, ?)", [(eid, *x) for x in d.get("pasos", [])])
                con.executemany("insert into eventos(entrega_id, at, origen, texto) values (?, ?, ?, ?)", [(eid, *x) for x in d.get("eventos", [])])
                con.execute("insert into eventos(entrega_id, at, origen, texto) values (?, ?, 'script', ?)",
                            (eid, ahora, f"Detalle de la entrega recuperado desde {d['origen']}"))
    con.close()
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, help="archivo de la base (por defecto, el de la plataforma)")
    ap.add_argument("--respaldo", type=Path, action="append", help="un respaldo concreto (se puede repetir); por defecto todos los de data/respaldos")
    ap.add_argument("--aplicar", action="store_true", help="escribe los cambios (antes guarda una copia de la base)")
    ap.add_argument("--reconstruir", action="store_true", help="para entregas más nuevas que los respaldos: arma sus líneas desde el cubicaje guardado")
    a = ap.parse_args()
    base = a.base or _base_por_defecto()
    if not base.exists():
        print(f"No encuentro la base: {base}")
        return 1
    respaldos = a.respaldo or sorted((p for p in (base.parent / "respaldos").glob("*.db") if not p.name.startswith("antes-de-recuperar")),
                                     key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"Base: {base}\nRespaldos a revisar: {len(respaldos)}")
    r = recuperar(base, respaldos, a.aplicar, a.reconstruir)
    print(f"\nEntregas sin detalle: {r['sin_detalle']}")
    for e, d in r["recuperadas"].items():
        print(f"  {'recuperada' if a.aplicar else 'se recuperaría'}  {e}: {d['lineas']} SKU, {d['unidades']} un.  ← {d['origen']}")
    if r["sin_resolver"]:
        print(f"\nQuedan {len(r['sin_resolver'])} sin recuperar: {', '.join(r['sin_resolver'])}")
        print("  (son más nuevas que los respaldos" + ("" if a.reconstruir else "; prueba con --reconstruir") + "). Las puedes volver a cargar con «Editar entrega»")
    if r["recuperadas"] and not a.aplicar:
        print("\nNo se cambió nada. Para hacerlo, vuelve a correr el comando con --aplicar.")
    if r["copia"]:
        print(f"\nListo. Copia de la base antes de recuperar: {r['copia']}")
        print("Los pasos de las entregas reconstruidas (cita pedida, confirmada…) hay que volver a marcarlos si no venían de un respaldo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
