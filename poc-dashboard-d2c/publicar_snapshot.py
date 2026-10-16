"""Agente de publicacion: corre DENTRO de la red (donde se alcanzan las bases), con credenciales de SOLO LECTURA.

  1. Extrae las tablas de VTEX (Azure) y del ODS de SAP.
  2. Ejecuta los controles de calidad: si algo FALLA, no publica (se puede dejar una excepcion escrita con --excepcion "motivo").
  3. Minimiza columnas, empaqueta, cifra (SNAPSHOT_KEYS) y sube a Vercel Blob (BLOB_READ_WRITE_TOKEN) o a una carpeta (SNAPSHOT_DIR).
  4. Deja la publicacion en la bitacora de auditoria y avisa por ALERTA_WEBHOOK si algo falla.

Uso:   python publicar_snapshot.py                 publica una vez
       python publicar_snapshot.py --cada 300      repite cada 300 s (con reintentos y aviso de fallas)
       python publicar_snapshot.py --demo          usa los datos de ejemplo (prueba de punta a punta)
       python publicar_snapshot.py --simular       extrae y valida pero no sube nada
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request

import pandas as pd

from app import auditoria, calidad, maestra, queries, snapshot
from app.config import settings


def _codigo() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip() or "sin-git"
    except Exception:  # noqa: BLE001
        return "sin-git"


def _avisar(texto: str) -> None:
    print("  [ALERTA] " + texto, flush=True)
    if settings.alerta_webhook.startswith("https://"):
        try:
            req = urllib.request.Request(settings.alerta_webhook, data=json.dumps({"text": "Dashboard D2C · " + texto}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=15).read()  # noqa: S310
        except Exception as e:  # noqa: BLE001
            print(f"  (no se pudo enviar el aviso: {e})", flush=True)


def extraer(demo: bool) -> tuple[dict, pd.Timestamp]:
    if demo:
        from app.demo import datos_demo, lineas_demo, maestra_demo
        o, i, s, f, st, h = datos_demo()
        return dict(orders=o, items=i, sap=s, fact=f, stock=st, items_todos=lineas_demo(), maestra=maestra_demo()), h
    t0 = time.time()
    fr = {"orders": queries.q_orders(), "items": queries.q_order_items(), "sap": queries.q_sap_ingresos(), "fact": queries.q_facturacion(),
          "stock": queries.q_stock_vtex(), "items_todos": queries.q_items_todos()}
    m, err, _ = maestra.cargar()
    fr["maestra"] = m if m is not None else pd.DataFrame(columns=["SKU", "Clasif2", "Producto"])
    if m is None:
        print(f"  (sin maestra de productos: {err})", flush=True)
    print(f"  extraccion lista en {time.time() - t0:.1f} s", flush=True)
    return fr, queries.q_hoy_cl()


def publicar_una_vez(demo: bool, simular: bool, excepcion: str | None) -> int:
    fr, hoy = extraer(demo)
    q = calidad.evaluar(fr["orders"], fr["items"], fr["sap"], fr["fact"], fr["stock"], hoy, settings.fecha_validada)
    print(f"  calidad: {q['ok']} ok, {q['alertas']} alertas, {q['fallas']} fallas (puntaje {q['puntaje']})", flush=True)
    for c in q["controles"]:
        if c["estado"] != "ok":
            print(f"    [{c['estado'].upper()}] {c['id']} {c['regla']}: {c['detalle']}", flush=True)
    if q["fallas"] and not excepcion:
        auditoria.registrar("publicacion_rechazada", None, fallas=[c["id"] for c in q["controles"] if c["estado"] == "falla"])
        _avisar(f"Publicación RECHAZADA por {q['fallas']} control(es) de calidad en falla. Revisa los datos de origen.")
        return 2
    paquete, man = snapshot.empaquetar(fr, hoy, q, excepcion, _codigo())
    print(f"  paquete {man['id']}: {len(paquete) / 1024:.0f} KB cifrados, huella {man['huella'][:12]}", flush=True)
    if simular:
        print("  (simulacro: no se subio nada)", flush=True)
        return 0
    snapshot.publicar(paquete, man)
    auditoria.registrar("publicacion_ok", None, id=man["id"], huella=man["huella"][:16], pedidos=int(len(fr["orders"])),
                        fallas=q["fallas"], alertas=q["alertas"], excepcion=excepcion)
    print("  publicado.", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--cada", type=int, default=0, help="repetir cada N segundos")
    ap.add_argument("--excepcion", default=None, help="motivo escrito para publicar aunque haya controles en falla (queda en la bitacora y el manifiesto)")
    a = ap.parse_args()
    if not (settings.snapshot_keys and (settings.snapshot_dir or settings.blob_token)) and not a.simular:
        print("Faltan SNAPSHOT_KEYS y SNAPSHOT_DIR o BLOB_READ_WRITE_TOKEN en el .env (ver SEGURIDAD.md).")
        return 1
    fallos = 0
    while True:
        print(time.strftime("[%Y-%m-%d %H:%M:%S] publicando..."), flush=True)
        try:
            rc = publicar_una_vez(a.demo, a.simular, a.excepcion)
            fallos = 0 if rc == 0 else fallos + 1
        except Exception as e:  # noqa: BLE001
            fallos += 1
            auditoria.registrar("publicacion_error", None, error=str(e)[:200])
            if fallos in (1, 3) or fallos % 12 == 0:        # avisa al primer fallo, al tercero y luego cada hora aprox (sin inundar)
                _avisar(f"La publicación de datos falló ({fallos} seguidas): {str(e)[:150]}")
            rc = 1
        if not a.cada:
            return rc
        time.sleep(min(a.cada * (2 ** min(fallos, 3)), 3600) if fallos else a.cada)       # reintento con espera creciente


if __name__ == "__main__":
    sys.exit(main())
