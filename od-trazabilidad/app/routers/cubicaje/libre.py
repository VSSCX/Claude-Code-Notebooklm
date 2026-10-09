"""Cubicador libre: carga armada a mano, sin pedido ni SAP."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import domain
from ...db import get_session
from ...integrations import clientes as cli_mod
from ...integrations import kits as kits_mod
from ...integrations import medidas as med_mod
from ..comun import _aplicar_ajustes, _calefones_de, _clave_analisis, camiones_vista
from ._comun import (
    _commit,
    _datos_visor,
    _faltantes_de,
    _lineas_sin_kits,
    _visor_vivo,
    _xlsx_faltantes,
)

router = APIRouter()


@router.get("/cubicaje-libre/faltantes.xlsx")
def faltantes_libre(s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    c = s.get(Config, "cubicaje_libre")
    lineas = (_json.loads(c.valor).get("lineas") if c else None) or []
    conocidos = {m[0].lower() for m in med_mod.filas_para_cubicaje(s)}
    faltantes = _faltantes_de(lineas, lambda sku: sku.lower() in conocidos)
    if not faltantes:
        raise HTTPException(404, "Todos los productos de la carga tienen medidas.")
    return _xlsx_faltantes(faltantes, "medidas_faltantes.xlsx")


@router.get("/cubicaje-libre")
def get_cubicaje_libre(s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    c = s.get(Config, "cubicaje_libre")
    doc = _json.loads(c.valor) if c else {"lineas": [], "cliente": "", "modo": "MDA",
                                          "vista": "rampla"}
    doc["visor_vivo"] = _visor_vivo()        # la página abre el visor antes del primer cálculo
    if doc["visor_vivo"] and doc.get("lineas"):
        doc["visor_json"] = _datos_visor("libre_datos")
    return doc


@router.post("/cubicaje-libre/desde-pedido")
def cubicaje_desde_pedido(body: dict, s: Session = Depends(get_session)):
    """Trae al cubicador las líneas de un pedido ya analizado, para editarlas a mano."""
    import json as _json

    from ...models import Config
    numero = str(body.get("pedido", "")).strip()
    if not numero:
        raise HTTPException(422, "Falta el número de pedido.")
    ca = s.get(Config, _clave_analisis(numero))
    if ca is None:
        raise HTTPException(422, f"El pedido {numero} no está analizado. Analízalo en la pestaña "
                                 f"Pedidos y vuelve acá.")
    an = _json.loads(ca.valor)
    lineas = [{"sku": f["sku"], "qty": f["carga"]} for f in an["resultado"]["filas"]
              if (f.get("carga") or 0) > 0]
    if not lineas:
        raise HTTPException(422, "El análisis de ese pedido no tiene carga.")
    return cubicaje_libre({"lineas": lineas, "cliente": an.get("cliente", ""),
                           "modo": body.get("modo") or "MDA", "vista": body.get("vista") or "rampla",
                           "caja_master": body.get("caja_master") or "", "pedido": numero}, s)


def _reubicar(p, dx: float, dy: float, dz: float):
    """Copia una colocación moviéndola al origen del pallet."""
    from dataclasses import replace
    return replace(p, container=1, x=p.x - dx, y=p.y - dy, z=max(p.z - dz, 0.0))


def _merge_resultados(partes: list, pallet: list) -> dict:
    """Une varios cubicajes (los fijados a un camión y el resto) renumerando camiones."""
    camiones, filas, filas04, pallets, placed, avisos = [], [], [], [], [], []
    sin_medidas, sin_ubicar = [], {}
    for r in partes:
        off_cam = len(camiones)
        off_pal = len(pallets)
        for c in r.camiones:
            camiones.append({"numero": c.numero + off_cam, "tipo": c.tipo, "L": c.L, "w": c.w,
                             "h": c.h, "vol_m3": c.vol_m3})
        for f in r.filas03:
            d = dict(f.__dict__)
            d["camion"] += off_cam
            filas.append(d)
        for f in r.filas04:
            d = dict(f.__dict__)
            d["vehiculo"] += off_cam
            d["pallet"] = d["pallet"] + off_pal if d["pallet"] else 0
            filas04.append(d)
        for pl in r.pallets:
            d = dict(pl)
            d["numero"] += off_pal
            d["vehiculo"] += off_cam
            pallets.append(d)
        for p in r.placed:
            p.container += off_cam
            placed.append(p)
        avisos += r.avisos
        sin_medidas += r.sin_medidas
        sin_ubicar.update(r.sin_ubicar)
    return {"camiones": camiones, "filas": filas, "filas04": filas04, "pallets_detalle": pallets,
            "placed": placed, "avisos": avisos, "sin_medidas": sin_medidas,
            "sin_ubicar": sin_ubicar, "pallet": list(pallet),
            "unidades": sum(f["unidades"] for f in (filas04 or filas))}


def _reparto_por_grupos(grupos: list) -> list:
    """Cada grupo es un bloque, en orden numérico; lo que no trae grupo va al final."""
    from ...cubicaje.mda_predist import FilaPredist
    numeros = sorted({int(x.get("grupo") or 0) for x in grupos if int(x.get("grupo") or 0) > 0})
    ancho = len(str(numeros[-1])) if numeros else 1       # con ceros a la izquierda "GRUPO 02" ordena antes que "GRUPO 10"
    def etiqueta(g):
        return f"GRUPO {g:0{max(ancho, 2)}d}" if g else "SIN GRUPO"
    orden = sorted(grupos, key=lambda x: (int(x.get("grupo") or 0) or 10 ** 9))
    return [FilaPredist(sucursal=etiqueta(int(x.get("grupo") or 0)), sku=domain.norm_sku(x.get("sku")),
                        unidades=float(x.get("qty") or 0)) for x in orden]


def _avisos_reparto(lineas: list, pre: list) -> list[str]:
    """Reglas del predistribuido: la carga de cada SKU es el tope del reparto, y lo que no tiene sucursal no se carga."""
    carga: dict[str, float] = {}
    for l in lineas:
        sku = domain.norm_sku(l.get("sku"))
        carga[sku] = carga.get(sku, 0) + float(l.get("qty") or 0)
    repartido: dict[str, float] = {}
    for f in pre:
        repartido[f.sku] = repartido.get(f.sku, 0) + f.unidades
    sobran = {k: carga[k] - v for k, v in repartido.items() if k in carga and v < carga[k]}
    pasan = {k: v - carga.get(k, 0) for k, v in repartido.items() if v > carga.get(k, 0)}
    sin_reparto = {k: v for k, v in carga.items() if k not in repartido and v > 0}
    av = []
    if pasan:
        av.append("El reparto supera la carga en " + ", ".join(f"{k} (+{v:g})" for k, v in list(pasan.items())[:6])
                  + ": se recorta en el orden del archivo (las últimas sucursales quedan cortas).")
    if sobran or sin_reparto:
        resto = {**sobran, **sin_reparto}
        av.append("Sin sucursal asignada, no se cargan: " + ", ".join(f"{k} ({v:g} un.)" for k, v in list(resto.items())[:6])
                  + (" …" if len(resto) > 6 else ""))
    return av


@router.post("/cubicaje-libre")
def cubicaje_libre(body: dict, s: Session = Depends(get_session)):
    """Cubica una carga armada a mano: sin pedido, sin SAP.

    Con reparto por sucursal (predistribuido), las unidades por SKU son el tope de carga.
    """
    from datetime import date as _date

    from ...cubicaje.datos import cargar_cache_dims, leer_camiones
    from ...cubicaje.mda import Posicion
    from ...cubicaje.mda_predist import FilaPredist
    from ...cubicaje.motor import Entrada, ModoNoPortado, segmentar
    from ...cubicaje.visor import construir_json

    cliente = str(body.get("cliente") or "").strip().upper()
    from ...cubicaje.motor import resolver_destino
    piso_elegido = str(body.get("piso_pallet") or "")
    modo_elegido = str(body.get("modo") or "MDA").strip().upper()        # lo que eligió el usuario, antes de Destino y de la vista
    modo = resolver_destino(str(body.get("modo") or "MDA").strip().upper(), body.get("destino"))
    vista = str(body.get("vista") or "rampla").strip().lower()
    lineas = [x for x in (body.get("lineas") or []) if str(x.get("sku", "")).strip()]

    ajustes = _aplicar_ajustes(s)
    regla = cli_mod.buscar(s, cliente) if cliente else None
    pallet = tuple(cli_mod.doc(regla)["pallet"]) if regla else (120.0, 100.0, 140.0)
    med_filas = med_mod.filas_para_cubicaje(s)
    if not med_filas:
        raise HTTPException(422, "No hay Base de Medidas cargada: impórtala en SAP y archivos.")
    cache = cargar_cache_dims(med_filas)

    if vista == "pallet":
        # Un pallet solo: se cubica normal (en pallets) y después se muestra uno.
        # En MDA no existen pallets, así que para esta vista se usa el motor de pallets.
        body = {**body, "piso_pallet": ""}          # ver un pallet exige pallets: "a piso" no aplica
        if "SDA" not in modo:
            modo = "SDA PREDISTRIBUIDO" if "PREDISTRIBUIDO" in modo else "SDA STOCK"
            # los modos SDA exigen indicar caja master: si no viene, se asume sin caja
            if not str(body.get("caja_master") or "").strip():
                body = {**body, "caja_master": "SIN CAJA MASTER"}
        camiones = leer_camiones([list(camiones_vista(s)["rampla"])])
    elif vista == "camion50":
        camiones = leer_camiones([list(camiones_vista(s)["camion50"])])
    else:
        camiones = leer_camiones([list(camiones_vista(s)["rampla"])])

    kits = kits_mod.definiciones(s)
    posiciones = []
    desconocidos = []
    for i, l in enumerate(lineas):
        sku = domain.norm_sku(l.get("sku"))
        d = cache.get(sku.lower())
        if d is None and sku in kits:                       # un kit se cubica con las medidas de sus componentes
            faltan_k = [c for c, _ in kits[sku].componentes if cache.get(c.lower()) is None]
            if faltan_k:
                desconocidos += [c for c in faltan_k if c not in desconocidos]
            else:
                posiciones.append(Posicion(sku=sku, desc=kits[sku].desc or sku, carga=float(l.get("qty") or 0),
                                           pedido=str(body.get("pedido") or "LIBRE"), fila=i + 1))
            continue
        if d is None:
            desconocidos.append(sku)
            continue
        posiciones.append(
            Posicion(sku=sku, desc=d.desc or sku, carga=float(l.get("qty") or 0),
                     pedido=str(body.get("pedido") or "LIBRE"), fila=i + 1))

    pre = [FilaPredist(sucursal=str(x.get("sucursal", "")).strip().upper(),
                       sku=domain.norm_sku(x.get("sku")), unidades=float(x.get("qty") or 0))
           for x in (body.get("predistribuido") or [])
           if cache.get(domain.norm_sku(x.get("sku")).lower()) is not None
           or domain.norm_sku(x.get("sku")) in kits]      # sin medidas no se reparte

    # Grupos de carga: el 1 va al fondo y cada grupo empieza donde terminó el anterior. Es el mismo mecanismo
    # de bloques de un predistribuido, con el grupo en lugar de la sucursal.
    grupos = [x for x in (body.get("grupos") or []) if cache.get(domain.norm_sku(x.get("sku")).lower()) is not None]
    por_grupos = bool(grupos) and not pre and str(body.get("destino") or "").upper() != "STOCK"
    if por_grupos:
        pre = _reparto_por_grupos(grupos)
        if "PREDISTRIBUIDO" not in modo:
            modo = "SDA PREDISTRIBUIDO" if "SDA" in modo else "MDA PREDISTRIBUIDO"

    partes = []
    if posiciones:
        entrada = Entrada(cliente=cliente or "SIN CLIENTE", modo=modo, posiciones=posiciones,
                          pedidos=[str(body.get("pedido") or "LIBRE")], medidas=cache,
                          camiones=camiones,
                          # los modos que no son MDA exigen indicarla: sin dato se parte en "sin caja master"
                          caja_master=str(body.get("caja_master") or (regla.caja_master if regla else "")
                                          or ("SIN CAJA MASTER" if modo != "MDA" else "")),
                          piso_pallet=str(body.get("piso_pallet") or ""),
                          calefones=_calefones_de(cliente, s), predistribuido=pre, pallet=pallet,
                          hibrido=regla.hibrido if regla else None,
                          orientacion_pallet=ajustes["orientacion_pallet"],
                          capacidad_pallet=ajustes.get("capacidad_pallet", "geometria"),
                          kits=kits, kits_mezclar=bool(ajustes.get("kits_mezclar")))
        try:
            partes.append(segmentar(entrada))
        except (ModoNoPortado, ValueError) as e:
            raise HTTPException(422, str(e)) from e

    base = _merge_resultados(partes, list(pallet)) if partes else {
        "camiones": [], "filas": [], "filas04": [], "pallets_detalle": [], "placed": [],
        "avisos": [], "sin_medidas": [], "sin_ubicar": {}, "pallet": list(pallet), "unidades": 0}
    placed = base.pop("placed")
    from ...cubicaje.visor import PALETA
    from ...cubicaje.visor import letra as _letra
    # La letra y el color son los mismos que dibuja el visor: se asignan por orden de carga
    orden, n = {}, 0
    skus_carga = {domain.norm_sku(x.get("sku")) for x in lineas}
    for pl in placed:
        # la caja master (C + sku) se muestra con la letra de su producto
        cod = pl.cod[1:] if pl.cod.startswith("C") and pl.cod[1:] in skus_carga else pl.cod
        if cod not in orden:
            orden[cod] = (_letra(n), PALETA[n % len(PALETA)])
            n += 1
    detalle = {}
    siguiente = len(orden)          # los productos sin colocar siguen la serie: no repiten letra ni color
    for l in lineas:
        sku = domain.norm_sku(l.get("sku"))
        d = cache.get(sku.lower())
        if sku not in orden:
            orden[sku] = (_letra(siguiente), PALETA[siguiente % len(PALETA)])
            siguiente += 1
        letra, color = orden[sku]
        if d is not None:
            dc = cache.get(("c" + sku).lower())
            # caja master: C + el SKU del producto suelto (o una "C…" con varias piezas)
            es_master = sku[:1] in ("C", "c") and (cache.get(sku[1:].lower()) is not None or int(d.piezas or 1) > 1)
            detalle[sku] = {"piezas": int(d.piezas or 1), "master": es_master,
                            "caja": int(dc.piezas or 1) if dc is not None else 0,
                            "descripcion": d.desc or sku,
                            "medidas": f"{d.L:g} × {d.w:g} × {d.h:g} cm",
                            "apilable": d.apilable, "peso": d.peso,
                            "letra": letra, "color": color}
    doc = {**base, "cliente": cliente, "modo": modo_elegido, "vista": vista, "lineas": lineas,
           "detalle_lineas": detalle,
           "caja_master": str(body.get("caja_master") or ""), "piso_pallet": piso_elegido,
           "predistribuido": body.get("predistribuido") or [], "pedido": body.get("pedido") or "",
           "destino": str(body.get("destino") or ""),
           "generado": _date.today().isoformat(), "ajustes": ajustes,
           "desconocidos": desconocidos, "modo_usado": modo,
           "faltantes": _faltantes_de(_lineas_sin_kits([(x.get("sku"), x.get("qty") or 0) for x in lineas], kits),
                                      lambda sku: cache.get(sku.lower()) is not None)}

    # Las cajas master cuentan como un bulto con varias unidades: 10 cajas de 4 = 40 unidades en 10 bultos.
    # El motor coloca cajas; aquí las unidades de cada fila y el total se llevan a unidades de producto.
    por_caja = {k: v["piezas"] for k, v in detalle.items() if v.get("master") and v["piezas"] > 1}
    if por_caja:
        for lista in (doc.get("filas") or [], doc.get("filas04") or []):
            for f in lista:
                m = por_caja.get(str(f.get("sku")))
                if m:
                    f["bultos"] = f.get("bultos") or f["unidades"]
                    f["unidades"] = f["unidades"] * m
        doc["unidades"] = sum(f["unidades"] for f in (doc.get("filas04") or doc.get("filas") or []))
    doc["por_caja_master"] = por_caja
    if "PREDISTRIBUIDO" in modo and pre:
        doc["avisos"] = list(doc.get("avisos") or []) + _avisos_reparto(lineas, pre)
    if por_grupos:
        n_grupos = len({x.sucursal for x in pre})
        doc["avisos"] = [f"Cubicado en {n_grupos} grupos: el primero va al fondo y cada grupo empieza donde terminó el anterior."
                         + (" En pallets, cada grupo arma sus pallets." if "SDA" in modo and not piso_elegido == "PISO" else ""),
                         *(doc.get("avisos") or [])]
    doc["grupos"] = body.get("grupos") or []

    try:
        from pathlib import Path as _Path

        from ...config import settings as _st
        from ...cubicaje.mda import Camion as _Cam
        from ...cubicaje.sda import TARIMA
        from ...cubicaje.visor import (
            asegurar_visor_vivo,
            guardar_datos_visor,
            html_visor,
            preparar_carpeta,
        )
        carpeta = Path(_st.visores_dir)
        preparar_carpeta(carpeta, _st.visor_assets)
        pallets_visor = doc["pallets_detalle"]
        if vista == "pallet":
            todos = sorted({p.pallet for p in placed if p.pallet})
            n_pal = int(body.get("pallet_n") or (todos[0] if todos else 0))
            if n_pal not in todos:
                n_pal = todos[0] if todos else 0
            geo = next((x for x in doc["pallets_detalle"] if x["numero"] == n_pal), None)
            doc["pallet_visto"] = n_pal
            doc["pallets_disponibles"] = todos
            doc["pallet_camion"] = bool(body.get("pallet_camion"))
            doc["pallet_vehiculo"] = (geo or {}).get("vehiculo", 0)       # camión donde va el pallet elegido
        if vista == "pallet" and not body.get("pallet_camion"):
            # Se aísla el pallet elegido: sus cajas se mueven al origen y se dibuja su tarima
            dx = geo["x"] if geo else 0.0
            dy = geo["y"] if geo else 0.0
            # Se mueven al origen en X e Y, pero la altura se conserva: las cajas van
            # apoyadas sobre la tarima, no atravesándola.
            placed = [_reubicar(p, dx, dy, 0.0) for p in placed if p.pallet == n_pal]
            cams = [_Cam(numero=1, tipo=f"Pallet {n_pal}", L=pallet[1], w=pallet[0],
                         h=pallet[2] + TARIMA)]
            pallets_visor = [{"numero": n_pal, "vehiculo": 1, "x": 0.0, "y": 0.0,
                              "dl": pallet[1], "dw": pallet[0],
                              "tipo": (geo or {}).get("tipo", ""),
                              "sucursal": (geo or {}).get("sucursal", "")}]
            if n_pal:
                doc["camiones"] = [{"numero": n_pal, "tipo": "Pallet", "L": pallet[1],
                                    "w": pallet[0], "h": pallet[2],
                                    "vol_m3": pallet[0] * pallet[1] * pallet[2] / 1_000_000}]
                dentro = [f for f in doc["filas04"] if f.get("pallet") == n_pal]
                vol = pallet[0] * pallet[1] * pallet[2] / 1_000_000 or 1
                usado = sum(p.volM3 for p in placed)      # lo que ocupan sus cajas
                doc["filas"] = [{**f, "camion": n_pal, "tipo_camion": "Pallet",
                                 "cap_m3": round(vol, 2), "ocup_linea": usado / vol,
                                 "ocup_acum": usado / vol,
                                 "libre_m3": 0, "pedido": "", "pedidos_camion": "",
                                 "tipo_carga": f.get("tipo", ""), "descripcion": f["descripcion"],
                                 "sku": f["sku"], "unidades": f["unidades"],
                                 "fila_origen": 0, "sucursal": f.get("sucursal", "")}
                                for f in dentro]
        else:
            cams = ([_Cam(numero=c["numero"], tipo=c["tipo"], L=c["L"], w=c["w"], h=c["h"])
                     for c in doc["camiones"]] or
                    [_Cam(numero=1, tipo=camiones[0].tipo, L=camiones[0].L, w=camiones[0].w,
                          h=camiones[0].h)])
        plantilla = _Path(_st.plantilla_visor).read_text(encoding="utf-8")
        datos_visor = construir_json(placed, cams, es_sda=bool(pallets_visor), pallets=pallets_visor, modo=modo,
                                    por_caja=por_caja)
        html = html_visor(plantilla, datos_visor)
        for viejo in carpeta.glob("libre_*.html"):
            viejo.unlink(missing_ok=True)
        nombre_fs = f"libre_{uuid.uuid4().hex[:8]}.html"
        (carpeta / nombre_fs).write_text(html, encoding="utf-8")
        doc["visor"] = f"/visor/{nombre_fs}"
        doc["visor_vivo"] = asegurar_visor_vivo(carpeta, plantilla)
        guardar_datos_visor(carpeta, "libre_datos", datos_visor)
    except Exception as e:  # noqa: BLE001
        doc["visor"] = ""
        doc["avisos"] = list(doc["avisos"]) + [f"No se pudo generar el visor: {str(e)[:150]}"]

    domain.guardar_config(s, "cubicaje_libre", doc)             # sin visor_json: va en su archivo
    _commit(s)
    if doc.get("visor_vivo"):
        doc["visor_json"] = datos_visor
    return doc
