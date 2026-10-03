"""SAP: leer, analizar, crear y borrar."""
import math
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import domain
from ..db import get_session
from ..integrations import acciones, bases, clientes as cli_mod, maestra, medidas as med_mod
from sqlalchemy import select

from ..models import Archivo, Entrega
from ..schemas import EntregaIn, PaqueteIn, PedidoIn




def _commit(s: Session):
    try:
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(409, "El registro choca con otro existente.") from e

from .comun import (AJUSTES_DEFECTO, CAMIONES_DEFECTO, CAMIONES_VISTA, _ajustes_cubicaje,
                    _aplicar_ajustes, _calefones_de, _clave_analisis, _clave_cubicaje)

router = APIRouter()

@router.post("/paquetes")
def post_paquete(body: PaqueteIn, s: Session = Depends(get_session)):
    """Recibe el paquete que envía TrazWeb.bas al terminar cada macro."""
    res = domain.cargar_paquete(s, body)
    _commit(s)
    return res


@router.post("/sap/leer_pedido", status_code=202)
def sap_leer_pedido(body: dict):
    """Lee un pedido de VL01N con Python (sin Excel). Solo lectura."""
    from datetime import date as _date
    import re as _re
    from ..integrations import sap
    pedido = str(body.get("pedido", "")).strip()
    puesto = str(body.get("puesto", "")).strip().upper()
    fecha = str(body.get("fecha", "")).strip()
    cliente = str(body.get("cliente", "")).strip()
    if not _re.fullmatch(r"\d{4,12}", pedido):
        raise HTTPException(422, "N° de pedido inválido.")
    if not _re.fullmatch(r"[A-Z0-9]{2,6}", puesto):
        raise HTTPException(422, "Puesto de expedición inválido (ejemplo: PN01).")
    try:
        f = _date.fromisoformat(fecha) if fecha else _date.today()
    except ValueError as e:
        raise HTTPException(422, "Fecha inválida.") from e

    def leer(avance):
        avance("Leyendo VL01N")
        lectura = sap.leer_pedido(pedido, puesto, f.strftime("%d.%m.%Y"))
        if not lectura.posiciones:
            raise RuntimeError(lectura.aviso or "El pedido no devolvió posiciones.")
        posiciones = [{"sku": x.sku, "qty_entrega": x.qty_entrega, "qty_pendiente": x.qty_pendiente}
                      for x in lectura.posiciones]
        from ..db import SessionLocal
        with SessionLocal() as ses:
            res = domain.cargar_lectura_sap(ses, pedido, cliente, posiciones)
            ses.commit()
        res["aviso"] = lectura.aviso
        return res

    try:
        return acciones.lanzar_python("sap_leer_pedido", "Leer pedido desde SAP (directo)",
                                      [pedido], leer)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/analisis/{numero}", status_code=202)
def analizar(numero: str, body: dict):
    import json as _json
    import re as _re
    from datetime import date as _date
    from ..analisis import calcular, codigo_cliente, en_entrega_por_modelo, grupo_sop
    from ..config import BASE_DIR
    from ..db import SessionLocal
    from ..integrations import base_medidas, sap

    puesto = str(body.get("puesto", "")).strip().upper()
    cliente = str(body.get("cliente", "")).strip().upper()
    if not _re.fullmatch(r"\d{4,12}", numero):
        raise HTTPException(422, "N° de pedido inválido.")
    if not _re.fullmatch(r"[A-Z0-9]{2,6}", puesto):
        raise HTTPException(422, "Puesto de expedición inválido (ejemplo: PN01).")
    if not cliente:
        raise HTTPException(422, "Falta el cliente.")
    try:
        f = _date.fromisoformat(str(body.get("fecha") or "")) if body.get("fecha") else _date.today()
    except ValueError as e:
        raise HTTPException(422, "Fecha inválida.") from e

    def correr(avance):
        avance("1/4 Leyendo el pedido en VL01N")
        lectura = sap.leer_pedido(numero, puesto, f.strftime("%d.%m.%Y"))
        if not lectura.posiciones:
            raise RuntimeError(lectura.aviso or "El pedido no devolvió posiciones.")
        posiciones = [{"sku": domain.norm_sku(x.sku), "qty_entrega": x.qty_entrega,
                       "qty_pendiente": x.qty_pendiente} for x in lectura.posiciones]

        if lectura.aviso:
            avance("Aviso de SAP: " + lectura.aviso[:80])
        avance("2/4 Consultando Qty en entrega en ZSD001_03")
        carpeta = BASE_DIR / "data" / "sap"
        filas_zsd = sap.zsd001_03(codigo_cliente(cliente), [p["sku"] for p in posiciones],
                                  str(carpeta), "Qty En Entrega.xlsx")

        avance("3/4 Calculando saldos y alertas")
        grupo = grupo_sop(cliente)
        plan = bases.plan_sop(grupo)
        disp = bases.disponibilidad()
        med = base_medidas.medidas()
        en_ent = en_entrega_por_modelo(filas_zsd)
        res = calcular(posiciones, plan, en_ent, med, disp)

        stock = {}
        if res["alertadas"]:
            stock = sap.mmbe(res["alertadas"], lambda t: avance("4/4 " + t))
            res = calcular(posiciones, plan, en_ent, med, disp, stock)
        else:
            avance("4/4 Sin alertas: no se consulta MMBE")

        skus = [p["sku"] for p in posiciones]
        # Se guardan los datos usados, para recalcular ajustes sin volver a SAP
        doc = {"pedido": numero, "cliente": cliente, "grupo_sop": grupo, "puesto": puesto,
               "fecha": f.isoformat(), "posiciones": posiciones, "en_entrega": en_ent,
               "plan": {k: plan[k] for k in skus if k in plan},
               "medidas": {k: med[k] for k in skus if k in med},
               "disponibilidad": {k: disp[k] for k in skus if k in disp},
               "stock": stock, "ajustes": {}, "resultado": res,
               "generado": _date.today().isoformat()}
        with SessionLocal() as ses:
            domain.cargar_lectura_sap(ses, numero, cliente, posiciones)
            domain.guardar_config(ses, _clave_analisis(numero), doc)
            ses.commit()
        return {"pedido": numero, "posiciones": len(posiciones), "alertadas": len(res["alertadas"]),
                "aviso_sap": lectura.aviso}

    try:
        return acciones.lanzar_python("analizar_pedido", "Analizar pedido", [numero], correr)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/analisis/{numero}")
def get_analisis(numero: str, s: Session = Depends(get_session)):
    import json as _json
    from ..models import Config
    c = s.get(Config, _clave_analisis(numero))
    if c is None:
        raise HTTPException(404, "Este pedido todavía no tiene análisis.")
    return _json.loads(c.valor)


@router.put("/analisis/{numero}/carga")
def ajustar_carga(numero: str, body: dict, s: Session = Depends(get_session)):
    """Ajuste manual de la CARGA de un SKU (como editar la columna F del Excel)."""
    import json as _json
    from ..analisis import calcular
    from ..models import Config
    c = s.get(Config, _clave_analisis(numero))
    if c is None:
        raise HTTPException(404, "Este pedido todavía no tiene análisis.")
    doc = _json.loads(c.valor)
    sku = domain.norm_sku(body.get("sku", ""))
    if sku not in {p["sku"] for p in doc["posiciones"]}:
        raise HTTPException(422, "Ese SKU no está en el análisis.")
    if body.get("carga") in (None, ""):
        doc["ajustes"].pop(sku, None)                    # volver al valor calculado
    else:
        try:
            carga = float(body["carga"])
        except (TypeError, ValueError) as e:
            raise HTTPException(422, "Cantidad inválida.") from e
        if not math.isfinite(carga) or carga < 0:
            raise HTTPException(422, "La cantidad no puede ser negativa ni infinita.")
        doc["ajustes"][sku] = carga
    # Recalcula con los mismos datos guardados (no vuelve a consultar SAP)
    doc["resultado"] = calcular(doc["posiciones"], doc["plan"], doc["en_entrega"], doc["medidas"],
                                doc["disponibilidad"], doc["stock"], doc["ajustes"])
    domain.guardar_config(s, _clave_analisis(numero), doc)
    _commit(s)
    # Cubicaje en vivo: si el pedido ya estaba cubicado, se rehace con la carga nueva
    cubicaje = None
    from ..models import Config as _Cfg
    prev = s.get(_Cfg, _clave_cubicaje(numero))
    if prev is not None:
        from .cubicaje import _cubicar
        anterior = _json.loads(prev.valor)
        try:
            cubicaje = _cubicar(numero, {"modo": anterior.get("modo"),
                                         "caja_master": anterior.get("caja_master", ""),
                                         "piso_pallet": anterior.get("piso_pallet", "")}, s)
        except HTTPException as e:
            cubicaje = {"error": e.detail}
    return {**doc, "cubicaje": cubicaje}


@router.post("/sap/crear_entregas", status_code=202)
def sap_crear_entregas(body: dict, s: Session = Depends(get_session)):
    """Crea en SAP una entrega por camión, con las cantidades del cubicaje del pedido."""
    import json as _json
    from datetime import date as _date
    from ..integrations import sap_crear
    from ..models import Config
    numero = str(body.get("pedido", "")).strip()
    ensayo = bool(body.get("ensayo", True))
    puesto = str(body.get("puesto", "")).strip().upper()
    camiones_pedidos = body.get("camiones") or []
    c = s.get(Config, _clave_cubicaje(numero))
    if c is None:
        raise HTTPException(422, "Primero hay que cubicar el pedido.")
    cub = _json.loads(c.valor)
    if not puesto:
        an = s.get(Config, _clave_analisis(numero))
        puesto = (_json.loads(an.valor).get("puesto", "") if an else "").upper()
    if not puesto:
        raise HTTPException(422, "Falta el puesto de expedición (PN01, PN02…).")
    if not ensayo and str(body.get("confirmar", "")).strip() != numero:
        raise HTTPException(422, "Para crear de verdad hay que confirmar escribiendo el pedido.")

    # Un camión = una entrega: {camión: {sku: unidades}}
    por_camion: dict[int, dict] = {}
    for f in cub["filas"]:
        if camiones_pedidos and f["camion"] not in camiones_pedidos:
            continue
        por_camion.setdefault(f["camion"], {})
        por_camion[f["camion"]][f["sku"]] = por_camion[f["camion"]].get(f["sku"], 0) + f["unidades"]
    if not por_camion:
        raise HTTPException(422, "El cubicaje no tiene camiones para crear.")
    fecha = str(body.get("fecha") or _date.today().strftime("%d.%m.%Y"))

    def correr(avance):
        salidas = []
        for i, (cam, materiales) in enumerate(sorted(por_camion.items()), start=1):
            avance(f"{'Ensayo' if ensayo else 'Creando'} camión {cam} ({i} de {len(por_camion)})")
            r = sap_crear.crear_entrega(numero, puesto, fecha, materiales,
                                        fecha_cita=str(body.get("fecha_cita") or ""),
                                        hora_cita=str(body.get("hora_cita") or ""), ensayo=ensayo)
            salidas.append({"camion": cam, "ok": r.ok, "entrega": r.entrega, "mensaje": r.mensaje,
                            "pasos": r.pasos, "borradas": r.borradas, "ajustadas": r.ajustadas,
                            "incidencias": r.incidencias})
            if r.ok and r.entrega and not ensayo:
                # La entrega ya existe en SAP y no se puede deshacer: si no se alcanza a registrar aquí,
                # se avisa con su número para cargarla a mano y se sigue con los demás camiones.
                try:
                    from ..db import SessionLocal
                    with SessionLocal() as ses:
                        from ..schemas import EntregaIn
                        domain.guardar_entrega(ses, EntregaIn(
                            entrega=r.entrega, pedido=numero, grupo="",
                            lineas=[{"sku": k, "qty": v} for k, v in materiales.items()]))
                        ses.commit()
                except Exception as err:  # noqa: BLE001
                    salidas[-1]["incidencias"] = list(r.incidencias or []) + [
                        f"Creada en SAP, pero no se pudo registrar en la plataforma: {str(err)[:150]}"]
            if not r.ok:
                break                      # ante el primer problema se detiene
        errores = [x for x in salidas if not x["ok"]]
        if errores:
            raise RuntimeError(errores[0]["mensaje"])
        return {"pedido": numero, "ensayo": ensayo, "resultados": salidas}

    try:
        return acciones.lanzar_python("crear_entregas",
                                      f"{'Ensayo de entregas' if ensayo else 'Crear entregas'} {numero}",
                                      [numero], correr)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/sap/crear_grupo", status_code=202)
def sap_crear_grupo(body: dict, s: Session = Depends(get_session)):
    """Crea el grupo de transporte de un camión (VL06), igual que el paso del Excel."""
    from ..integrations import sap_crear
    entregas = [str(x).strip() for x in (body.get("entregas") or []) if str(x).strip()]
    ensayo = bool(body.get("ensayo", True))
    camion = str(body.get("camion") or "1")
    cliente = str(body.get("cliente") or "")
    referencia = str(body.get("referencia") or "")
    if not entregas:
        raise HTTPException(422, "No hay entregas para agrupar.")
    if not ensayo and str(body.get("confirmar", "")).strip().lower() != "agrupar":
        raise HTTPException(422, "Para crear el grupo hay que confirmar escribiendo 'agrupar'.")

    def correr(avance):
        avance(f"{'Ensayo' if ensayo else 'Creando grupo'} del camión {camion} "
               f"({len(entregas)} entregas)")
        r = sap_crear.crear_grupo(entregas, referencia=referencia, ensayo=ensayo,
                                  cliente=cliente, camion=camion)
        if not r.ok:
            raise RuntimeError(r.mensaje)
        if r.grupo:
            from ..db import SessionLocal
            with SessionLocal() as ses:
                for n in entregas:
                    e = ses.scalar(select(Entrega).where(Entrega.entrega == n))
                    if e is not None:
                        e.grupo = r.grupo
                        domain._log(e, f"Agrupada en {r.grupo} desde la plataforma", "web")
                        e.actualizado = domain.ahora()
                ses.commit()
        return {"grupo": r.grupo, "ensayo": ensayo, "mensaje": r.mensaje, "pasos": r.pasos,
                "incidencias": r.incidencias}

    try:
        return acciones.lanzar_python("crear_grupo", f"Grupo del camión {camion}", entregas, correr)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/sap/fecha_grupo", status_code=202)
def sap_fecha_grupo(body: dict, s: Session = Depends(get_session)):
    """Fecha, hora y referencia de la cita de un grupo (VG02), como el paso del Excel."""
    from datetime import date as _date
    from ..integrations import sap_crear
    grupo = str(body.get("grupo", "")).strip()
    fecha = str(body.get("fecha", "")).strip()
    hora = str(body.get("hora", "")).strip()
    referencia = str(body.get("referencia", "")).strip()
    ensayo = bool(body.get("ensayo", True))
    if not grupo:
        raise HTTPException(422, "Falta el número de grupo.")
    if not (fecha or hora or referencia):
        raise HTTPException(422, "Indica al menos fecha, hora o referencia.")

    def correr(avance):
        avance(f"{'Ensayo' if ensayo else 'Actualizando'} la cita del grupo {grupo}")
        r = sap_crear.actualizar_grupo(grupo, fecha, hora, referencia, ensayo=ensayo)
        if not r.ok:
            raise RuntimeError(r.mensaje)
        if not ensayo:
            from ..db import SessionLocal
            with SessionLocal() as ses:
                for e in ses.scalars(select(Entrega).where(Entrega.grupo == grupo)).all():
                    if fecha:
                        try:
                            d, m, a = fecha.split(".")
                            e.cita_fecha = _date(int(a), int(m), int(d))
                        except ValueError:
                            pass
                    if hora:
                        e.cita_hora = hora[:5]
                    if referencia:
                        e.cita_numero = referencia
                    domain._log(e, f"Cita en SAP: {fecha} {hora} {referencia}".strip(), "web")
                    e.actualizado = domain.ahora()
                ses.commit()
        return {"grupo": grupo, "ensayo": ensayo, "mensaje": r.mensaje, "pasos": r.pasos,
                "incidencias": r.incidencias}

    try:
        return acciones.lanzar_python("fecha_grupo", f"Cita del grupo {grupo}", [grupo], correr)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/sap/borrar_entrega", status_code=202)
def sap_borrar_entrega(body: dict, s: Session = Depends(get_session)):
    """Borra la entrega en SAP (VL06) y recién entonces la quita de la plataforma."""
    import re as _re
    from ..integrations import sap
    entrega = str(body.get("entrega", "")).strip()
    if not _re.fullmatch(r"\d{4,12}", entrega):
        raise HTTPException(422, "N° de entrega inválido.")
    if str(body.get("confirmar", "")).strip() != entrega:
        raise HTTPException(422, "Falta confirmar escribiendo el número de la entrega.")
    e = s.scalar(select(Entrega).where(Entrega.entrega == entrega))
    if e is None:
        raise HTTPException(404, "Esa entrega no está en la plataforma.")
    if domain.paso_ok(e, "facturada"):
        raise HTTPException(422, "La entrega está facturada: no se puede borrar.")

    def correr(avance):
        avance("Borrando en SAP (VL06)")
        ok, mensaje = sap.borrar_entrega(entrega)
        from ..db import SessionLocal
        with SessionLocal() as ses:
            if ok:
                domain.borrar_entrega(ses, entrega)
                ses.commit()
        if not ok:
            raise RuntimeError(mensaje)
        return {"entrega": entrega, "mensaje": mensaje, "borrada": True}

    try:
        return acciones.lanzar_python("borrar_entrega", f"Borrar entrega {entrega} en SAP",
                                      [entrega], correr)
    except RuntimeError as err:
        raise HTTPException(409, str(err)) from err


@router.post("/sap/borrar_grupo", status_code=202)
def sap_borrar_grupo(body: dict, s: Session = Depends(get_session)):
    """Borra el grupo en SAP (VG02). Las entregas quedan sin grupo, no se borran."""
    import re as _re
    from ..integrations import sap
    grupo = str(body.get("grupo", "")).strip()
    if not _re.fullmatch(r"\d{3,12}", grupo):
        raise HTTPException(422, "N° de grupo inválido.")
    if str(body.get("confirmar", "")).strip() != grupo:
        raise HTTPException(422, "Falta confirmar escribiendo el número del grupo.")

    def correr(avance):
        avance("Borrando el grupo en SAP (VG02)")
        ok, mensaje = sap.borrar_grupo(grupo)
        from ..db import SessionLocal
        with SessionLocal() as ses:
            if ok:
                for e in ses.scalars(select(Entrega).where(Entrega.grupo == grupo)).all():
                    e.grupo = ""
                    domain._log(e, f"Grupo {grupo} borrado en SAP", "web")
                    e.actualizado = domain.ahora()
                ses.commit()
        if not ok:
            raise RuntimeError(mensaje)
        return {"grupo": grupo, "mensaje": mensaje, "borrado": True}

    try:
        return acciones.lanzar_python("borrar_grupo", f"Borrar grupo {grupo} en SAP",
                                      [grupo], correr)
    except RuntimeError as err:
        raise HTTPException(409, str(err)) from err


@router.get("/acciones")
def get_acciones():
    return acciones.disponibles()


@router.post("/acciones/{accion_id}", status_code=202)
def run_accion(accion_id: str, body: dict | None = None):
    args = [str(x) for x in (body or {}).get("args", [])]
    try:
        return acciones.lanzar(accion_id, args)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/acciones/trabajos/{tid}")
def get_trabajo(tid: str, s: Session = Depends(get_session)):
    t = acciones.trabajo(tid)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    # El visor generado queda registrado en el pedido la primera vez que se consulta
    if t.get("archivo") and not t.get("registrado"):
        pedido = t["args"][0] if t["args"] else ""
        domain.registrar_archivo(s, pedido, "", "visor", "Visor 3D del cubicaje", t["archivo"])
        _commit(s)
        t["registrado"] = True
    return t
