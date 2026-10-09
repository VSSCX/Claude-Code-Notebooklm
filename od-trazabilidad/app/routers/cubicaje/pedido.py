"""Cubicaje de un pedido y cubicaje conjunto de varios."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import domain
from ...db import get_session
from ...integrations import clientes as cli_mod
from ...integrations import kits as kits_mod
from ...integrations import medidas as med_mod
from ..comun import (
    _aplicar_ajustes,
    _calefones_de,
    _clave_analisis,
    _clave_cubicaje,
    camiones_defecto,
    camiones_vista,
)
from ._comun import (
    _commit,
    _datos_visor,
    _faltantes_de,
    _lineas_sin_kits,
    _resumen_kits,
    _xlsx_faltantes,
)
from .predistribuido import _clave_predist

router = APIRouter()


@router.get("/cubicaje/{numero}")
def get_cubicaje(numero: str, s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    c = s.get(Config, _clave_cubicaje(numero))
    if c is None:
        raise HTTPException(404, "Este pedido todavía no está cubicado.")
    doc = _json.loads(c.valor)
    if doc.get("visor_vivo"):
        doc["visor_json"] = _datos_visor(f"pedido_{numero}_datos")
    return doc


@router.get("/cubicaje/{numero}/faltantes.xlsx")
def faltantes_pedido(numero: str, s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    ca = s.get(Config, _clave_analisis(numero))
    if ca is None:
        raise HTTPException(404, "Este pedido todavía no tiene análisis.")
    filas = _json.loads(ca.valor)["resultado"]["filas"]
    conocidos = {m[0].lower() for m in med_mod.filas_para_cubicaje(s)}
    faltantes = _faltantes_de([{"sku": f["sku"], "qty": f["carga"]} for f in filas if f["carga"] > 0],
                              lambda sku: sku.lower() in conocidos)
    if not faltantes:
        raise HTTPException(404, "Todos los productos del pedido tienen medidas.")
    return _xlsx_faltantes(faltantes, f"medidas_faltantes_{numero}.xlsx")


@router.post("/cubicaje/{numero}")
def cubicar(numero: str, body: dict, s: Session = Depends(get_session)):
    return _cubicar(numero, body or {}, s)


def _id_conjunto(numeros: list[str]) -> str:
    """Identificador estable de un grupo de pedidos cubicados juntos (el mismo conjunto da siempre el mismo código)."""
    import hashlib
    return "J" + hashlib.sha1("|".join(sorted(numeros)).encode()).hexdigest()[:6].upper()


def _cubicar(numero, body: dict, s: Session):
    """Cubica con la carga del análisis (incluidos los ajustes manuales).
    `numero` puede ser un pedido o varios: con varios se cubican JUNTOS en los mismos camiones (los conchos de un
    pedido viajan con otro), como el multipedido del Excel."""
    import json as _json
    from datetime import date as _date

    from ...cubicaje.datos import cargar_cache_dims, leer_camiones
    from ...cubicaje.mda import Posicion
    from ...cubicaje.mda_predist import FilaPredist
    from ...cubicaje.motor import Entrada, ModoNoPortado, segmentar
    from ...cubicaje.visor import construir_json
    from ...integrations import base_medidas
    from ...models import Config

    numeros = [str(numero)] if isinstance(numero, str) else [str(x) for x in dict.fromkeys(numero)]
    multi = len(numeros) > 1
    if not numeros:
        raise HTTPException(422, "No hay pedidos para cubicar.")
    analisis = {}
    for n in numeros:
        ca = s.get(Config, _clave_analisis(n))
        if ca is None:
            raise HTTPException(422, f"Primero hay que analizar el pedido {n}: la carga sale del análisis."
                                if multi else "Primero hay que analizar el pedido: la carga sale del análisis.")
        analisis[n] = _json.loads(ca.valor)
    numero = numeros[0]
    an = analisis[numero]
    filas = [f for n in numeros for f in analisis[n]["resultado"]["filas"]]
    if not filas:
        raise HTTPException(422, "El análisis no tiene productos.")
    cid = _id_conjunto(numeros) if multi else ""

    cfg = s.get(Config, "app")
    cfg_val = _json.loads(cfg.valor) if cfg else {}
    camiones_cfg = body.get("camiones") or cfg_val.get("camiones") or camiones_defecto(s)
    modo = str(body.get("modo") or an.get("modo_cubicaje") or "MDA").strip().upper()
    # Pedidos de clientes distintos (p. ej. regionales): se cubican juntos con las reglas de un cliente
    # (pallet, caja master, híbrido); por defecto el del primer pedido, o el que elija el analista.
    clientes_pedidos = {n: (analisis[n].get("cliente") or "").strip() for n in numeros}
    distintos = list(dict.fromkeys(c for c in clientes_pedidos.values() if c))
    cliente = (str(body.get("cliente") or "").strip() or an.get("cliente", "")) if multi else an.get("cliente", "")

    med_filas = med_mod.filas_para_cubicaje(s)          # la cargada en la plataforma
    origen_medidas = "plataforma"
    if not med_filas:                                    # si no hay, se lee el archivo de red
        med_filas = base_medidas.filas()
        origen_medidas = "archivo de red"
    if not med_filas:
        raise HTTPException(422, "No hay Base de Medidas: impórtala en la pestaña SAP y archivos.")

    ajustes = _aplicar_ajustes(s)
    regla = cli_mod.buscar(s, cliente)
    kits = kits_mod.definiciones(s)
    entrada = Entrada(
        kits=kits, kits_mezclar=bool(ajustes.get("kits_mezclar")),
        cliente=cliente, modo=modo,
        posiciones=[Posicion(sku=f["sku"], desc=f["descripcion"], carga=f["carga"],
                             pedido=n, fila=i + 5)
                    for i, (n, f) in enumerate((n, f) for n in numeros for f in analisis[n]["resultado"]["filas"])],
        pedidos=numeros, medidas=cargar_cache_dims(med_filas),
        camiones=leer_camiones(camiones_cfg),
        caja_master=str(body.get("caja_master") or (regla.caja_master if regla else "")),
        pallet=tuple(cli_mod.doc(regla)["pallet"]) if regla else None,
        hibrido=regla.hibrido if regla else None,
        pallet_por_producto=bool(regla.pallet_por_producto) if regla else False,
        orientacion_pallet=ajustes["orientacion_pallet"],
        capacidad_pallet=ajustes.get("capacidad_pallet", "geometria"),
        piso_pallet=str(body.get("piso_pallet") or ""),
        calefones=set(body.get("calefones") or set().union(*(_calefones_de(c, s) for c in (distintos or [cliente])))),
        predistribuido=[FilaPredist(sucursal=f["sucursal"], sku=f["sku"], unidades=f["unidades"],
                                    por_bulto=int(f.get("por_bulto") or 0))
                        for f in _json.loads(pre.valor)["filas"]]
        if not multi and (pre := s.get(Config, _clave_predist(numero))) else [])
    try:
        r = segmentar(entrada)
    except ModoNoPortado as e:
        raise HTTPException(422, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    avisos_cli = _avisos_clientes(s, distintos, cliente) if multi else []
    doc = {"pedido": numero if not multi else " + ".join(numeros), "cliente": cliente, "modo": r.modo,
           "generado": _date.today().isoformat(),
           "conjunto": {"id": cid, "pedidos": numeros, "clientes": clientes_pedidos,
                        "distintos": distintos, "reglas_de": cliente} if multi else None,
           "caja_master": entrada.caja_master, "piso_pallet": entrada.piso_pallet,
           "pallet": list(entrada.pallet or (120.0, 100.0, 140.0)),
           "camiones": [{"numero": c.numero, "tipo": c.tipo, "L": c.L, "w": c.w, "h": c.h,
                         "vol_m3": c.vol_m3} for c in r.camiones],
           "filas": [f.__dict__ for f in r.filas03],
           "filas04": [f.__dict__ for f in r.filas04],
           "pallets_detalle": r.pallets,
           "avisos": avisos_cli + list(r.avisos), "sin_medidas": r.sin_medidas, "no_encontrados": r.no_encontrados,
           "sin_ubicar": r.sin_ubicar, "unidades": r.unidades, "origen_medidas": origen_medidas,
           "ajustes": ajustes,
           "kits": _resumen_kits(kits, [(f["sku"], f["carga"]) for f in filas if f["carga"] > 0]),
           "faltantes": _faltantes_de(_lineas_sin_kits([(f["sku"], f["carga"]) for f in filas if f["carga"] > 0], kits),
                                      lambda sku, _c=entrada.medidas: _c.get(sku.lower()) is not None)}
    nombre_visor = f"conjunto_{cid}" if multi else f"pedido_{numero}"
    if not multi:
        domain.guardar_config(s, _clave_cubicaje(numero), doc)

    # Visor 3D: misma plantilla del Excel, servida desde la plataforma con sus librerías
    doc["visor"] = ""
    try:
        from pathlib import Path as _Path

        from ...config import settings as _st
        from ...cubicaje.visor import (
            asegurar_visor_vivo,
            guardar_datos_visor,
            html_visor,
            preparar_carpeta,
        )
        carpeta = Path(_st.visores_dir)
        faltan = preparar_carpeta(carpeta, _st.visor_assets)
        if faltan:
            doc["avisos"] = list(doc["avisos"]) + [
                "Al visor le faltan librerías (" + ", ".join(faltan) + "). "
                "Revisa VISOR_ASSETS en el archivo .env."]
        plantilla = _Path(_st.plantilla_visor).read_text(encoding="utf-8")
        from ...cubicaje.mda import Camion as _Cam
        # Sin carga no se dibuja una plantilla en blanco: se muestra la rampla vacía
        rm = camiones_vista(s)["rampla"]
        cams = r.camiones or [_Cam(numero=1, tipo=rm[0], L=rm[1], w=rm[2], h=rm[3])]
        datos_visor = construir_json(r.placed, cams, es_sda=bool(r.pallets), pallets=r.pallets,
                                      cliente=cliente, modo=r.modo)
        html = html_visor(plantilla, datos_visor)
        for viejo in carpeta.glob(f"{nombre_visor}_*.html"):         # deja solo el último
            viejo.unlink(missing_ok=True)
        nombre_fs = f"{nombre_visor}_{uuid.uuid4().hex[:8]}.html"
        (carpeta / nombre_fs).write_text(html, encoding="utf-8")
        doc["visor"] = f"/visor/{nombre_fs}"
        # para la página: visor de dirección fija + los datos de este cálculo
        doc["visor_vivo"] = asegurar_visor_vivo(carpeta, plantilla)
        guardar_datos_visor(carpeta, f"{nombre_visor}_datos", datos_visor)
    except Exception as e:  # noqa: BLE001 - el cubicaje vale aunque el visor falle
        doc["avisos"] = list(doc["avisos"]) + [f"No se pudo generar el visor 3D: {str(e)[:150]}"]
    if multi:
        _guardar_conjunto(s, doc, numeros, cid)
    else:
        domain.guardar_config(s, _clave_cubicaje(numero), doc)  # sin visor_json: va en su archivo
        domain.anotar_flujo(s, numero, cubicaje=domain.resumen_cubicaje(doc))
    _commit(s)
    if doc.get("visor_vivo"):
        doc["visor_json"] = datos_visor
    return doc


def _avisos_clientes(s: Session, distintos: list[str], base: str) -> list[str]:
    """Aviso cuando los pedidos juntos son de clientes con reglas distintas: el cubicaje usa las de `base`."""
    if len(distintos) < 2:
        return []
    firmas = set()
    for c in distintos:
        r = cli_mod.buscar(s, c)
        firmas.add((r.pallet_largo, r.pallet_ancho, r.pallet_alto, r.caja_master, r.hibrido, r.calefon_aparte,
                   r.pallet_por_producto)
                   if r else None)
    if len(firmas) <= 1:
        return []
    return [f"Clientes con reglas distintas ({', '.join(distintos)}): el cubicaje usa las de {base or distintos[0]} "
            "(pallet, caja master, híbrido, un producto por pallet). Si corresponden otras, elígelas en «Reglas de» y vuelve a cubicar."]


def _guardar_conjunto(s: Session, doc: dict, numeros: list[str], cid: str) -> None:
    """Guarda el cubicaje conjunto y, para cada pedido, su parte: los camiones y las filas que le tocan (con la numeración
    de camiones compartida). Así crear entregas, el visor y el flujo de cada pedido funcionan como siempre."""
    por_pedido = {}
    for n in numeros:
        filas_n = [f for f in doc["filas"] if str(f.get("pedido")) == n]
        cams = sorted({f["camion"] for f in filas_n})
        por_pedido[n] = {"unidades": sum(f["unidades"] for f in filas_n), "camiones": cams}
    doc["por_pedido"] = por_pedido
    domain.guardar_config(s, f"conjunto:{cid}", doc)
    for n in numeros:
        mio = por_pedido[n]
        doc_n = {**doc, "pedido": n, "filas": [f for f in doc["filas"] if str(f.get("pedido")) == n],
                 "camiones": [c for c in doc["camiones"] if c["numero"] in mio["camiones"]],
                 "unidades": mio["unidades"]}
        domain.guardar_config(s, _clave_cubicaje(n), doc_n)
        domain.anotar_flujo(s, n, cubicaje=domain.resumen_cubicaje(doc_n))


@router.post("/cubicaje-conjunto")
def cubicar_conjunto(body: dict, s: Session = Depends(get_session)):
    """Cubica varios pedidos analizados juntos, en los mismos camiones."""
    pedidos = [str(x).strip() for x in (body.get("pedidos") or []) if str(x).strip()]
    if len(set(pedidos)) < 2:
        raise HTTPException(422, "Elige al menos dos pedidos para cubicarlos juntos.")
    return _cubicar(pedidos, {k: v for k, v in body.items() if k != "pedidos"}, s)


@router.get("/cubicaje-conjunto/{cid}")
def get_cubicaje_conjunto(cid: str, s: Session = Depends(get_session)):
    import json as _json

    from ...models import Config
    c = s.get(Config, f"conjunto:{cid}")
    if c is None:
        raise HTTPException(404, "Ese cubicaje conjunto no existe: vuelve a cubicar los pedidos juntos.")
    return _json.loads(c.valor)
