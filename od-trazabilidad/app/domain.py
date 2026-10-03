"""Reglas de negocio y traducción documento <-> tablas."""
import contextvars
import json
import re
import unicodedata
import zlib
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Archivo, Config, Entrega, Evento, LineaEntrega, LineaPedido, PasoEntrega, Pedido, ahora
from .schemas import EntregaIn, PaqueteIn, PedidoIn

EVENTOS = {
    "pedido": "pedido extraído de VL01N",
    "entregas": "entregas creadas",
    "grupos": "grupos creados",
    "fecha_sap": "fecha y cita actualizadas en SAP",
}
LOG_MAX = 40


class ErrorNegocio(ValueError):
    pass


# ---------- utilidades ----------
def norm_sku(s) -> str:
    s = str(s or "").strip()
    return re.sub(r"^0+(?=\d)", "", s)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def norm_vehiculo(v: str) -> str:
    n = _norm(v)
    if "rampla" in n:
        return "Rampla 53"
    if "cami" in n:
        return "Camión 50"
    return ""


def _iso(dt: datetime | None) -> str:
    return dt.isoformat(timespec="seconds") + "Z" if dt else ""


def _sin_tz(dt: datetime | None) -> datetime:
    if dt is None:
        return ahora()
    return dt.replace(tzinfo=None) if dt.tzinfo is None else dt.astimezone(tz=None).replace(tzinfo=None)


# ---------- lectura ----------
def pedido_doc(p: Pedido, maestra: dict[str, str] | None = None) -> dict:
    maestra = maestra or {}
    return {
        "pedido": p.pedido, "oc": p.oc, "cliente": p.cliente, "canal": p.canal,
        "fechaOC": p.fecha_oc.isoformat() if p.fecha_oc else "", "obs": p.obs,
        # La descripción guardada manda; si está vacía, se completa con la maestra
        "lineas": [{"sku": l.sku, "desc": l.descripcion or maestra.get(l.sku, ""), "qty": l.qty,
                    "externa": l.externa} for l in p.lineas],
        "creado": _iso(p.creado), "actualizado": _iso(p.actualizado),
    }


def entrega_doc(e: Entrega) -> dict:
    return {
        "entrega": e.entrega, "pedido": e.pedido_ref.pedido, "grupo": e.grupo, "tipo": e.tipo,
        "cita": {"numero": e.cita_numero, "fecha": e.cita_fecha.isoformat() if e.cita_fecha else "",
                 "hora": e.cita_hora},
        "vehiculo": e.vehiculo, "carga": e.carga, "un": e.un, "region": e.region,
        "factura": e.factura, "obs": e.obs, "anulada": e.anulada, "reprog": e.reprogramaciones,
        "lineas": [{"sku": l.sku, "qty": l.qty} for l in e.lineas],
        "pasos": {p.paso: {"ok": p.ok, "at": _iso(p.at)} for p in e.pasos},
        "log": [{"at": _iso(x.at), "txt": x.texto, "origen": x.origen} for x in e.eventos[:LOG_MAX]],
        "creado": _iso(e.creado), "actualizado": _iso(e.actualizado),
    }


def archivo_doc(a: Archivo, pedido: str) -> dict:
    return {"id": a.id, "pedido": pedido, "grupo": a.grupo, "tipo": a.tipo,
            "nombre": a.nombre, "url": f"/archivos/{a.id}", "at": _iso(a.at)}


def estado(s: Session) -> dict:
    """Todo lo que muestra la web, en pocas consultas de columnas y sin armar objetos del ORM:
    con miles de pedidos y su historial, crear los objetos era casi todo el tiempo de la respuesta.
    Debe dar lo mismo que pedido_doc / entrega_doc (hay una prueba que lo compara)."""
    from collections import defaultdict
    from .integrations import maestra
    desc = maestra.descripciones()
    P, LP, E, LE, PA, EV, A = (m.__table__ for m in (Pedido, LineaPedido, Entrega, LineaEntrega,
                                                    PasoEntrega, Evento, Archivo))

    lineas_p: dict[int, list] = defaultdict(list)
    for r in s.execute(select(LP.c.pedido_id, LP.c.sku, LP.c.descripcion, LP.c.qty, LP.c.externa)
                       .order_by(LP.c.id)):
        lineas_p[r.pedido_id].append({"sku": r.sku, "desc": r.descripcion or desc.get(r.sku, ""),
                                      "qty": r.qty, "externa": r.externa})
    numero_de: dict[int, str] = {}
    pedidos = []
    for r in s.execute(select(P)):
        numero_de[r.id] = r.pedido
        pedidos.append({"pedido": r.pedido, "oc": r.oc, "cliente": r.cliente, "canal": r.canal,
                        "fechaOC": r.fecha_oc.isoformat() if r.fecha_oc else "", "obs": r.obs,
                        "lineas": lineas_p.get(r.id, []),
                        "creado": _iso(r.creado), "actualizado": _iso(r.actualizado)})

    lineas_e: dict[int, list] = defaultdict(list)
    for r in s.execute(select(LE.c.entrega_id, LE.c.sku, LE.c.qty).order_by(LE.c.id)):
        lineas_e[r.entrega_id].append({"sku": r.sku, "qty": r.qty})
    pasos: dict[int, dict] = defaultdict(dict)
    for r in s.execute(select(PA.c.entrega_id, PA.c.paso, PA.c.ok, PA.c.at)):
        pasos[r.entrega_id][r.paso] = {"ok": r.ok, "at": _iso(r.at)}
    # solo las últimas LOG_MAX entradas de cada entrega, ya recortadas en la base
    orden = func.row_number().over(partition_by=EV.c.entrega_id,
                                   order_by=(EV.c.at.desc(), EV.c.id.desc())).label("n")
    ev = select(EV.c.entrega_id, EV.c.at, EV.c.texto, EV.c.origen, orden).subquery()
    log_e: dict[int, list] = defaultdict(list)
    for r in s.execute(select(ev).where(ev.c.n <= LOG_MAX).order_by(ev.c.entrega_id, ev.c.n)):
        log_e[r.entrega_id].append({"at": _iso(r.at), "txt": r.texto, "origen": r.origen})

    entregas = [{
        "entrega": r.entrega, "pedido": numero_de[r.pedido_id], "grupo": r.grupo, "tipo": r.tipo,
        "cita": {"numero": r.cita_numero, "fecha": r.cita_fecha.isoformat() if r.cita_fecha else "",
                 "hora": r.cita_hora},
        "vehiculo": r.vehiculo, "carga": r.carga, "un": r.un, "region": r.region,
        "factura": r.factura, "obs": r.obs, "anulada": r.anulada, "reprog": r.reprogramaciones,
        "lineas": lineas_e.get(r.id, []), "pasos": pasos.get(r.id, {}), "log": log_e.get(r.id, []),
        "creado": _iso(r.creado), "actualizado": _iso(r.actualizado),
    } for r in s.execute(select(E))]

    archivos = [{"id": r.id, "pedido": r.pedido or "", "grupo": r.grupo, "tipo": r.tipo,
                 "nombre": r.nombre, "url": f"/archivos/{r.id}", "at": _iso(r.at)}
                for r in s.execute(select(A.c.id, A.c.grupo, A.c.tipo, A.c.nombre, A.c.at, P.c.pedido)
                                   .select_from(A.outerjoin(P, A.c.pedido_id == P.c.id))
                                   .order_by(A.c.at.desc()))]
    return {
        "pedidos": pedidos, "entregas": entregas,
        "config": {c.clave: json.loads(c.valor or "{}")
                   for c in s.scalars(select(Config).where(_config_liviana())).all()},
        "archivos": archivos, "version": version(s),
    }


# Documentos grandes por pedido (análisis y cubicaje con todas sus filas): la web los pide de a uno.
# En /estado y en la versión solo viaja su resumen, en "flujo:<pedido>".
PESADAS = ("analisis:%", "cubicaje:%")


def resumen_analisis(doc: dict) -> dict:
    filas = (doc.get("resultado") or {}).get("filas", [])
    return {"generado": doc.get("generado", ""), "cliente": doc.get("cliente", ""),
            "grupo_sop": doc.get("grupo_sop", ""), "filas": len(filas),
            "limitadas": sum(1 for f in filas if f["carga_calculada"] < f["qty_entrega"]),
            "excedidas": sum(1 for f in filas if f.get("ajustada") and f["carga"] > f["carga_calculada"]),
            "pedida": sum(f["qty_entrega"] for f in filas), "carga": sum(f["carga"] for f in filas)}


def resumen_cubicaje(doc: dict) -> dict:
    return {"generado": doc.get("generado", ""), "camiones": len(doc.get("camiones") or []),
            "modo": doc.get("modo", "")}


def anotar_flujo(s: Session, pedido: str, **partes: dict) -> None:
    """Deja al día el resumen del flujo del pedido (análisis, cubicaje) que ve la web."""
    c = s.get(Config, f"flujo:{pedido}")
    actual = json.loads(c.valor) if c else {}
    actual.update(partes)
    guardar_config(s, f"flujo:{pedido}", actual)


def rellenar_flujo(s: Session) -> int:
    """Crea el resumen de los pedidos que se analizaron o cubicaron antes de que existiera."""
    existentes = set(s.scalars(select(Config.clave).where(Config.clave.like("flujo:%"))).all())
    n = 0
    for c in s.scalars(select(Config).where(Config.clave.like("analisis:%") | Config.clave.like("cubicaje:%"))).all():
        tipo, _, pedido = c.clave.partition(":")
        try:
            doc = json.loads(c.valor)
            parte = {"analisis": resumen_analisis(doc)} if tipo == "analisis" else {"cubicaje": resumen_cubicaje(doc)}
        except (ValueError, KeyError, TypeError):
            continue
        actual = json.loads(s.get(Config, f"flujo:{pedido}").valor) if f"flujo:{pedido}" in existentes else {}
        if tipo in actual:
            continue
        anotar_flujo(s, pedido, **parte)
        existentes.add(f"flujo:{pedido}")
        n += 1
    return n


def _config_liviana():
    from sqlalchemy import and_, not_
    return and_(*[not_(Config.clave.like(p)) for p in PESADAS])


def version(s: Session) -> str:
    """Cambia con cualquier alta, edición o borrado (para el polling de la web)."""
    partes = []
    for m in (Pedido, Entrega):
        n, mx = s.execute(select(func.count(), func.max(m.actualizado)).select_from(m)).one()
        partes.append(f"{n}:{_iso(mx)}")
    n_arch, mx_arch = s.execute(select(func.count(), func.max(Archivo.at)).select_from(Archivo)).one()
    partes.append(f"{n_arch}:{_iso(mx_arch)}")
    cfg = s.scalars(select(Config.valor).where(_config_liviana()).order_by(Config.clave)).all()
    partes.append(str(zlib.crc32("\x1f".join(cfg).encode())))
    return "|".join(partes)


# ---------- escritura ----------
def _get_pedido(s: Session, numero: str) -> Pedido | None:
    return s.scalar(select(Pedido).where(Pedido.pedido == numero))


def _get_entrega(s: Session, numero: str) -> Entrega | None:
    return s.scalar(select(Entrega).where(Entrega.entrega == numero))


def guardar_pedido(s: Session, d: PedidoIn) -> Pedido:
    p = _get_pedido(s, d.pedido) or Pedido(pedido=d.pedido, creado=ahora())
    if p.id is None:
        s.add(p)
    p.oc, p.cliente, p.canal, p.fecha_oc, p.obs = d.oc, d.cliente.upper(), d.canal, d.fechaOC, d.obs
    _sync_lineas_pedido(p, [(norm_sku(l.sku), l.desc, l.qty, l.externa) for l in d.lineas])
    p.actualizado = ahora()
    return p


def _sync_lineas_pedido(p: Pedido, filas: list[tuple[str, str, int, int]]):
    agregadas: dict[str, list] = {}
    for sku, desc, qty, ext in filas:
        a = agregadas.setdefault(sku, [desc, 0, 0])
        a[0] = a[0] or desc
        a[1] += qty
        a[2] += ext
    actuales = {l.sku: l for l in p.lineas}
    for sku, l in actuales.items():
        if sku not in agregadas:
            p.lineas.remove(l)
    for sku, (desc, qty, ext) in agregadas.items():
        l = actuales.get(sku)
        if l is None:
            p.lineas.append(LineaPedido(sku=sku, descripcion=desc, qty=qty, externa=ext))
        else:
            l.descripcion, l.qty, l.externa = desc, qty, ext


def _sync_lineas_entrega(e: Entrega, filas: list[tuple[str, int]]):
    agregadas: dict[str, int] = {}
    for sku, qty in filas:
        if qty > 0:
            agregadas[sku] = agregadas.get(sku, 0) + qty
    actuales = {l.sku: l for l in e.lineas}
    for sku, l in actuales.items():
        if sku not in agregadas:
            e.lineas.remove(l)
    for sku, qty in agregadas.items():
        if sku in actuales:
            actuales[sku].qty = qty
        else:
            e.lineas.append(LineaEntrega(sku=sku, qty=qty))


def _set_paso(e: Entrega, paso: str, ok: bool, at: datetime | None = None):
    actual = next((p for p in e.pasos if p.paso == paso), None)
    if actual is None:
        e.pasos.append(PasoEntrega(paso=paso, ok=ok, at=at or ahora()))
    elif actual.ok != ok:
        actual.ok, actual.at = ok, at or ahora()


def paso_ok(e: Entrega, paso: str) -> bool:
    return any(p.paso == paso and p.ok for p in e.pasos)


# Cada petición tiene su propio valor: si dos personas trabajan a la vez, el historial
# no se cruza (una variable común sí se pisaría entre peticiones simultáneas).
_usuario_actual: contextvars.ContextVar[str] = contextvars.ContextVar(
    "usuario_actual", default="sin nombre")


def usar_usuario(nombre: str) -> None:
    """Fija el nombre que queda en el historial de las acciones de esta petición."""
    _usuario_actual.set((str(nombre or "").strip()[:40]) or "sin nombre")


def usuario_actual() -> str:
    return _usuario_actual.get()


def _log(e: Entrega, texto: str, origen: str, at: datetime | None = None):
    """Anota en el historial qué pasó, desde dónde y quién lo hizo."""
    quien = usuario_actual() if origen in ("web", "script") else ""
    txt = f"{texto} — {quien}" if quien and quien != "sin nombre" else texto
    e.eventos.append(Evento(texto=txt[:300], origen=origen, at=at or ahora()))


def guardar_entrega(s: Session, d: EntregaIn) -> Entrega:
    p = _get_pedido(s, d.pedido)
    if p is None:
        raise ErrorNegocio(f"El pedido {d.pedido} no existe.")
    if not d.lineas or all(l.qty == 0 for l in d.lineas):
        raise ErrorNegocio("La entrega debe tener al menos un producto con cantidad.")
    if "confirmada" in d.pasos and d.pasos["confirmada"].ok and not (d.cita.fecha and d.cita.hora):
        raise ErrorNegocio("Para confirmar la cita se requiere fecha y hora.")
    if "facturada" in d.pasos and d.pasos["facturada"].ok and not d.factura:
        raise ErrorNegocio("Para marcar facturada se requiere el N° de factura.")

    e = _get_entrega(s, d.entrega) or Entrega(entrega=d.entrega, creado=ahora())
    nueva = e.id is None
    if nueva:
        s.add(e)
        _log(e, "Entrega creada", "web")      # queda quién la creó
    e.pedido_ref = p
    e.grupo, e.tipo, e.vehiculo, e.carga, e.un = d.grupo, d.tipo, d.vehiculo, d.carga, d.un
    e.region, e.factura, e.obs, e.anulada, e.reprogramaciones = d.region, d.factura, d.obs, d.anulada, d.reprog
    e.cita_numero, e.cita_fecha, e.cita_hora = d.cita.numero, d.cita.fecha, d.cita.hora
    _sync_lineas_entrega(e, [(norm_sku(l.sku), l.qty) for l in d.lineas])
    for k, v in d.pasos.items():
        _set_paso(e, k, v.ok, _sin_tz(v.at))
    # La web manda el historial completo: se agregan solo las entradas nuevas
    conocidas = {(_iso(x.at), x.texto) for x in e.eventos}
    for x in d.log:
        at = _sin_tz(x.at)
        if (_iso(at), x.txt) not in conocidas:
            _log(e, x.txt, "web", at)
    e.actualizado = ahora()
    return e


def borrar_pedido(s: Session, numero: str) -> bool:
    p = _get_pedido(s, numero)
    if p is None:
        return False
    s.delete(p)
    return True


def borrar_entrega(s: Session, numero: str) -> bool:
    e = _get_entrega(s, numero)
    if e is None:
        return False
    s.delete(e)
    return True


def registrar_archivo(s: Session, pedido: str, grupo: str, tipo: str, nombre: str, archivo: str) -> Archivo:
    p = _get_pedido(s, pedido) if pedido else None
    a = Archivo(pedido_id=p.id if p else None, grupo=grupo, tipo=tipo, nombre=nombre[:200], archivo=archivo)
    s.add(a)
    return a


def cargar_lectura_sap(s: Session, pedido: str, cliente: str, posiciones: list[dict]) -> dict:
    """Registra las posiciones leídas de VL01N. La cantidad del pedido nunca baja:
    si ya había un valor mayor (por ejemplo, desde el Excel), se conserva."""
    cliente = (cliente or "").upper()
    p = _get_pedido(s, pedido)
    nuevo = p is None
    if nuevo:
        pat = patron(s, cliente)
        p = Pedido(pedido=pedido, cliente=cliente, canal=pat["canal"], creado=ahora())
        s.add(p)
    elif cliente and not p.cliente:
        p.cliente = cliente
    actuales = {l.sku: l for l in p.lineas}
    agregadas = actualizadas = 0
    for pos in posiciones:
        sku = norm_sku(pos["sku"])
        qty = int(round(max(float(pos.get("qty_pendiente") or 0), 0)))
        fila = actuales.get(sku)
        if fila is None:
            p.lineas.append(LineaPedido(sku=sku, descripcion="", qty=qty, externa=0))
            agregadas += 1
        elif qty > fila.qty:
            fila.qty = qty
            actualizadas += 1
    p.actualizado = ahora()
    return {"pedido": pedido, "nuevo": nuevo, "agregadas": agregadas, "actualizadas": actualizadas,
            "posiciones": len(posiciones)}


def completar_oc(p: Pedido, oc: str) -> bool:
    """Pone la OC si el pedido no tiene. Una OC escrita a mano nunca se reemplaza."""
    oc = str(oc or "").strip()[:40]
    if not oc or p.oc:
        return False
    p.oc = oc
    return True


def borrar_archivos_por_nombre(s: Session, pedido: str, nombre: str, carpeta) -> int:
    """Quita versiones anteriores del mismo archivo (por ejemplo, el visor de un pedido)."""
    p = _get_pedido(s, pedido)
    if p is None:
        return 0
    viejos = s.scalars(select(Archivo).where(Archivo.pedido_id == p.id, Archivo.nombre == nombre)).all()
    for a in viejos:
        try:
            (carpeta / a.archivo).unlink(missing_ok=True)
        except OSError:
            pass
        s.delete(a)
    return len(viejos)


def asignar_archivo(s: Session, aid: int, grupo: str) -> Archivo | None:
    a = s.get(Archivo, aid)
    if a is not None:
        a.grupo = grupo
    return a


def guardar_config(s: Session, clave: str, valor: dict):
    c = s.get(Config, clave) or Config(clave=clave)
    c.valor = json.dumps(valor, ensure_ascii=False)
    s.add(c)


# ---------- patrón por cliente ----------
def patron(s: Session, cliente: str) -> dict:
    """Región y canal siguen lo último usado para ese cliente."""
    res = {"region": "RM", "canal": "RETAIL"}
    if not cliente:
        return res
    canal = s.scalar(select(Pedido.canal).where(Pedido.cliente == cliente, Pedido.canal != "")
                     .order_by(Pedido.actualizado.desc()).limit(1))
    region = s.scalar(select(Entrega.region).join(Pedido).where(Pedido.cliente == cliente)
                      .order_by(Entrega.actualizado.desc()).limit(1))
    return {"region": region or res["region"], "canal": canal or res["canal"]}


# ---------- paquete del script ----------
def cargar_paquete(s: Session, pk: PaqueteIn) -> dict:
    cliente = pk.cliente.upper()
    pat = patron(s, cliente)
    sap_ok = {str(g) for g in pk.sapOk}
    peds: dict[str, list] = {p.pedido: p.lineas for p in pk.pedidos}
    lineas_pedido_oc = {p.pedido: p.oc for p in pk.pedidos if p.oc}
    lineas_pedido_fecha = {p.pedido: p.fechaOC for p in pk.pedidos if p.fechaOC}
    for e in pk.entregas:
        if e.pedido and e.pedido not in peds:
            peds[e.pedido] = []

    n_ped = n_ent = 0
    for numero, lineas in peds.items():
        p = _get_pedido(s, numero)
        if p is None:
            p = Pedido(pedido=numero, cliente=cliente, canal=pat["canal"], creado=ahora())
            s.add(p)
        elif cliente and not p.cliente:
            p.cliente = cliente
        if lineas_pedido_oc.get(numero) and not p.oc:
            p.oc = lineas_pedido_oc[numero]
        if lineas_pedido_fecha.get(numero) and not p.fecha_oc:
            p.fecha_oc = lineas_pedido_fecha[numero]
        # Unidades que la plataforma ya conoce en entregas (para no contarlas dos veces)
        web: dict[str, int] = {}
        for e in p.entregas:
            if not e.anulada:
                for l in e.lineas:
                    web[l.sku] = web.get(l.sku, 0) + l.qty
        actuales = {l.sku: l for l in p.lineas}
        cambio = p.id is None
        for l in lineas:
            sku = norm_sku(l.sku)
            abierto = max(0, l.pendiente) + max(0, l.enEntrega)
            fila = actuales.get(sku)
            if fila is None:
                fila = LineaPedido(sku=sku, descripcion=l.desc, qty=0, externa=0)
                p.lineas.append(fila)
                actuales[sku] = fila
                cambio = True
            if abierto > fila.qty:          # la cantidad del pedido nunca baja por el script
                fila.qty, cambio = abierto, True
            if not fila.descripcion and l.desc:
                fila.descripcion, cambio = l.desc, True
            if pk.evento == "pedido":
                ext = max(0, l.enEntrega - web.get(sku, 0))
                if ext != fila.externa:
                    fila.externa, cambio = ext, True
        if cambio:
            p.actualizado = ahora()
            n_ped += 1
    s.flush()

    texto = f"Script SAP: {EVENTOS.get(pk.evento, pk.evento)}"
    for d in pk.entregas:
        p = _get_pedido(s, d.pedido)
        if p is None:
            continue
        e = _get_entrega(s, d.entrega)
        if e is None:
            e = Entrega(entrega=d.entrega, pedido_ref=p, region=pat["region"], creado=ahora())
            s.add(e)
        e.pedido_ref = p
        if d.grupo:
            e.grupo = d.grupo
        if norm_vehiculo(d.vehiculo):
            e.vehiculo = norm_vehiculo(d.vehiculo)
        if d.carga.upper() in ("MIX", "MONO"):
            e.carga = d.carga.upper()
        if pk.un.upper() in ("MDA", "SDA"):
            e.un = pk.un.upper()
        if pk.modalidad in ("Stock", "Predistribuido"):
            e.tipo = pk.modalidad
        if d.cita:
            e.cita_numero = d.cita
        if d.fecha:
            e.cita_fecha = d.fecha
        if re.fullmatch(r"\d{2}:\d{2}", d.hora or ""):
            e.cita_hora = d.hora
        if d.lineas:
            _sync_lineas_entrega(e, [(norm_sku(l.sku), l.qty) for l in d.lineas])
        # La fecha solo se actualiza en SAP con la cita ya confirmada por el cliente
        if e.grupo and e.grupo in sap_ok and e.cita_fecha:
            for k in ("solicitada", "confirmada", "sap"):
                if not paso_ok(e, k):
                    _set_paso(e, k, True)
        _log(e, texto, "script")
        e.actualizado = ahora()
        n_ent += 1
    return {"evento": pk.evento, "pedidos": n_ped, "entregas": n_ent}
