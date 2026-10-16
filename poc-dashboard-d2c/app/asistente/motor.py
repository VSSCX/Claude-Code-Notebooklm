"""Orquestador: pregunta -> plan (IA o reglas) -> validacion -> calculo -> respuesta. Ver ASISTENTE.md."""
from __future__ import annotations

import re
import threading
import time
from collections import deque

from app import servicio
from app.config import settings

from . import consulta, esquema, ia, memoria, reglas
from .redactar import EJEMPLOS, ayuda, frase, num, seguimientos
from .texto import sa

_LOCK = threading.Lock()
_LLAMADAS: deque = deque(maxlen=60)
info_motor = ia.info_motor


def _limite() -> bool:
    ahora = time.time()
    with _LOCK:
        while _LLAMADAS and ahora - _LLAMADAS[0] > 60:
            _LLAMADAS.popleft()
        if len(_LLAMADAS) >= 40:
            return False
        _LLAMADAS.append(ahora)
        return True


def _lineas():
    _, _, lin, info = servicio.lineas_todas()
    return lin, info


def _catalogo():
    """Catalogo para entender nombres de producto; None si las lineas no se pueden leer (se pide solo si hace falta)."""
    from app import maestra

    from . import catalogo
    try:
        return catalogo.de_union(_lineas()[0], maestra.cargar()[0])
    except Exception:  # noqa: BLE001
        return None


def _explicar(q: str, res: dict, notas: list) -> None:
    """Con IA_REDACTAR=1 la IA explica las cifras que el servidor ya calculo. Si cambia alguna cifra, se descarta y queda la frase base."""
    if not settings.ia_redactar or info_motor()["modo"] == "reglas":
        return
    try:
        t = ia.redactar(q, res)
    except Exception as e:  # noqa: BLE001
        t = None
        notas.append("La IA no pudo redactar la respuesta; va la versión base." + ("" if settings.serverless else f" ({str(e)[:80]})"))
    if t:
        res["texto_base"], res["texto"], res["redactada"] = res["texto"], t, True


def _charla(q: str, hoy, motor: str, dim) -> dict | None:
    """Gracias, chao y «que dia es hoy»: respuestas cortas que no pasan por el planificador."""
    from . import lexico as L
    qs = sa(q)
    f = lambda d: d.strftime("%d-%m-%Y")  # noqa: E731
    if re.search(L.P_GRACIAS, qs):
        return {"ok": True, "tipo": "texto", "texto": "De nada. Si quieres seguir, pregúntame por ventas, pedidos, stock o «qué debo revisar».", "chips": [], "notas": [], "motor": motor,
                "seguir": ["¿Hay algo raro hoy?", "¿Cómo vamos este mes?"]}
    if re.search(L.P_CHAO, qs):
        return {"ok": True, "tipo": "texto", "texto": "Hasta luego. Aquí estaré cuando quieras revisar los pedidos.", "chips": [], "notas": [], "motor": motor}
    if re.search(L.P_FECHA_HOY, qs):
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return {"ok": True, "tipo": "texto", "chips": [], "notas": [], "motor": motor, "seguir": ["¿Cuántos pedidos hay hoy?", "¿Cómo vamos este mes?"],
                "texto": f"Hoy es {dias[hoy.weekday()]} {f(hoy)} en el tablero; los datos llegan hasta el {f(dim['Creation_Date'].max())}."}
    return None


def _no_entendi(motor: str, aviso, q: str = "") -> dict:
    import difflib

    from . import lexico as L
    if q and not re.search(L.DOMINIO, sa(q)) and len(sa(q).split()) >= 3:
        return {"ok": False, "texto": "Eso queda fuera de lo que puedo responder: solo conozco los datos de VTEX y SAP del tablero (pedidos, ventas, stock, clientes, bodegas, entregas).",
                "ejemplos": EJEMPLOS, "motor": motor, "aviso": aviso, "fuera_de_alcance": True}
    cerca = difflib.get_close_matches(sa(q), [sa(e) for e in EJEMPLOS], n=1, cutoff=.55) if q else []
    pista = f" ¿Quisiste decir «{next(e for e in EJEMPLOS if sa(e) == cerca[0])}»?" if cerca else ""
    return {"ok": False, "texto": "No entendí la pregunta." + pista + " Puedo contar, sumar, listar y desglosar pedidos, unidades y montos por producto, "
            "cliente, bodega, status y período, y revisar el stock. Por ejemplo:", "ejemplos": EJEMPLOS, "motor": motor, "aviso": aviso}


def _pedido(plan: dict, motor: str) -> dict:
    det = servicio.detalle_pedido(plan["pedido"])
    if not det:
        return {"ok": False, "texto": f"No encontré el pedido {plan['pedido']} en los datos cargados.", "motor": motor}
    p, lin = det["pedido"], det["lineas"]
    fe = lambda s: f"{s[8:]}-{s[5:7]}-{s[:4]}" if s else "sin fecha"  # noqa: E731
    foco = plan.get("foco")
    nu = sum(x.get("qty") or 0 for x in lin)
    if foco == "lineas":
        texto = (f"El pedido {p['sequence']} tiene {len(lin)} línea{'s' if len(lin) != 1 else ''} y {num(nu)} unidad{'es' if nu != 1 else ''}"
                 f" por {num(p['monto'], '$')}." if lin else f"El pedido {p['sequence']} no tiene líneas de producto cargadas ({num(p['unidades'])} unidad(es) por {num(p['monto'], '$')}).")
    elif foco == "productos":
        det_l = "; ".join(f"{x['descripcion']} ×{num(x['qty'])}" + (f" ({num(x['monto'], '$')})" if x.get("monto") else "") for x in lin[:6])
        texto = (f"Pedido {p['sequence']}: {det_l}" + (f" y {len(lin) - 6} más" if len(lin) > 6 else "") + f". Total {num(p['monto'], '$')}."
                 if lin else f"El pedido {p['sequence']} no tiene líneas de producto cargadas.")
    elif foco == "estado":
        texto = (f"El pedido {p['sequence']} está {p['estado']} (status {p['status']}); " + (f"pedido SAP {p['pedido_sap']}" if p["pedido_sap"] else "todavía sin pedido SAP")
                 + (f"; causa del pendiente: {p['causa']}" if p.get("causa") else "") + f". Entrega estimada {fe(p['sed'])}.")
    else:
        texto = (f"Pedido {p['sequence']}: {p['estado']} (status {p['status']}), {p['cliente']}, bodega {p['warehouse']}, creado el {fe(p['fecha'])}, "
                 f"entrega estimada {fe(p['sed'])}, {num(p['unidades'])} unidad(es) por {num(p['monto'], '$')}"
                 + (f", pedido SAP {p['pedido_sap']}" if p["pedido_sap"] else ", todavía sin pedido SAP")
                 + (f". Causa de pendiente: {p['causa']}" if p.get("causa") else "") + ".")
    return {"ok": True, "tipo": "pedido", "texto": texto, "pedido": p, "lineas": lin, "chips": [], "notas": [det["aviso"]] if det.get("aviso") else [],
            "seguir": [f"productos del pedido {p['sequence']}", f"estado del pedido {p['sequence']}"] if not foco else [f"más pedidos de {p['cliente']}"], "motor": motor}


def _info(motor: str) -> dict:
    r = servicio.resumen_datos()
    f = lambda d: d.strftime("%d-%m-%Y")  # noqa: E731
    texto = (f"Hay {num(r['pedidos'])} pedidos cargados, creados entre el {f(r['desde'])} y el {f(r['hasta'])} (hoy es {f(r['hoy'])}). "
             f"Último pedido VTEX: {r['ultimo_pedido'] or 'sin dato'}. Última consulta a las bases: {r['consulta'] or 'sin dato'}"
             + (" (datos de ejemplo)." if r["demo"] else "."))
    return {"ok": True, "tipo": "texto", "texto": texto, "chips": [], "notas": [], "motor": motor}


def responder(pregunta: str, previo: dict | None = None, previas: list | None = None) -> dict:
    """Responde y deja la pregunta en el historial (res["id"] sirve para valorar la respuesta con el pulgar)."""
    q = re.sub(r"\s+", " ", str(pregunta or "")).strip()[:300]
    if not q:
        return {"ok": False, "texto": "Escribe una pregunta.", "motor": info_motor()["nombre"]}
    if not _limite():
        return {"ok": False, "texto": "Demasiadas consultas seguidas. Espera un minuto.", "motor": info_motor()["nombre"], "limite": True}
    res, ctx = _responder(q, previo if isinstance(previo, dict) else None, previas or [])
    res["id"] = memoria.registrar(q, ctx.get("plan"), bool(res.get("ok") or res.get("ayuda")), ctx.get("via", "reglas"),
                                  ctx.get("seguimiento", False), ctx.get("ignoradas"))
    return res


def _responder(q: str, previo: dict | None, previas: list | None = None) -> tuple[dict, dict]:
    motor = info_motor()["nombre"]
    dim, hoy = servicio.base_pedidos()
    K = esquema.conocidos(dim)
    charla = _charla(q, hoy, motor, dim)
    if charla:
        return charla, {"plan": None, "via": "reglas"}
    previo = esquema.validar(previo, K) if previo else None   # lo que manda el navegador nunca llega crudo al plan ni a la IA
    qn = memoria.normalizar(q)
    qn_ = qn
    empieza_y = qn.startswith("y ")

    plan, via, aviso, ban, nota_mem = None, "reglas", None, {"ignoradas": [], "correcciones": {}, "entendio": True}, None
    exacto = None if empieza_y else memoria.exacta(qn)
    if exacto:                                                   # la misma pregunta ya fue validada: se repite su plan con los datos de ahora
        plan, via = esquema.validar(exacto["plan"], K), "memoria"
    elif info_motor()["modo"] != "reglas":
        try:
            plan = ia.planificar(q, K, hoy, previo, memoria.parecidas(qn, 3, .4))
            if plan is None:
                aviso = "La IA no devolvió un plan válido, usé las reglas."
            else:
                via = "ia"
        except Exception as e:  # noqa: BLE001
            aviso = "La IA no respondió, usé las reglas." + ("" if settings.serverless else f" ({str(e)[:90]})")
    if plan is None:
        plan, ban = reglas.planificar(q, dim, hoy, previo, _catalogo, memoria.ruido())
        if not ban["entendio"]:
            parecida = memoria.parecidas(qn, 1, .7)               # no se entiende: se prueba con una pregunta parecida ya validada
            if not parecida:
                return _no_entendi(motor, aviso, q), {"plan": None, "via": via}
            plan, via = esquema.validar(parecida[0]["plan"], K), "memoria"
            nota_mem = f"Interpreté tu pregunta como «{parecida[0]['q']}», parecida a una que ya te sirvió."
    plan = esquema.validar(plan, K)
    accion = plan["accion"] or "medir"
    ctx = {"plan": plan, "via": via, "seguimiento": bool(ban.get("hereda")) or empieza_y, "ignoradas": ban["ignoradas"]}

    if accion == "ayuda":
        texto, ej = ayuda(saludo=bool(re.match(r"\s*(hola|buenas|hey|saludos)", sa(q))))
        return {"ok": False, "texto": texto, "ejemplos": ej, "motor": motor, "aviso": aviso, "tipo": "ayuda", "plan": plan, "ayuda": True}, ctx
    if accion == "info":
        return {**_info(motor), "plan": plan, "via": via, "aviso": aviso}, ctx
    if accion == "pedido":
        return {**_pedido(plan, motor), "plan": plan, "via": via, "aviso": aviso}, ctx
    try:
        res = (consulta.stock(plan, dim, hoy, _lineas, servicio.stock_vtex) if accion == "stock"
               else consulta.resumen(plan, dim, hoy, _lineas) if accion == "resumen"
               else consulta.sin_ventas(plan, dim, hoy, _lineas, servicio.stock_vtex) if accion == "sin_ventas"
               else consulta.alertas(plan, dim, hoy, _lineas, servicio.stock_vtex) if accion == "alertas"
               else consulta.medir_o_listar(plan, dim, hoy, _lineas))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "texto": "No pude calcular la respuesta." + ("" if settings.serverless else f" Detalle: {str(e)[:160]}"), "motor": motor, "plan": plan}, ctx

    solo_producto = plan["producto"] and not plan["accion"] and not any(
        plan[k] for k in ("periodo", "metrica", "agrupar", "estado", "cliente", "canal", "bodega", "sla"))
    if res.get("sin_producto") and via == "reglas" and solo_producto:      # una palabra suelta que no es un producto: no se entendio
        return _no_entendi(motor, aviso, q), {"plan": None, "via": via}
    notas = res.setdefault("notas", [])
    if nota_mem:
        notas.append(nota_mem)
    if via == "reglas" and memoria.rechazada(qn):
        notas.append("La última vez esta respuesta no te sirvió. Si tampoco es lo que buscas, reformula la pregunta o escribe «qué puedes hacer».")
    for a in ban.get("avisos", []):
        notas.append(a)
    if ban["correcciones"]:
        notas.append("Entendí " + ", ".join(f"«{a}» como «{b}»" for a, b in ban["correcciones"].items()) + ".")
    if ban["ignoradas"]:
        notas.append("No usé estas palabras: " + ", ".join(ban["ignoradas"]) + ".")
    if plan["periodo"] == "ultimos" and plan["dias"] == 30 and re.search(r"ultimo mes", sa(q)):
        notas.append("«El último mes» se tomó como los últimos 30 días; para el mes anterior completo pregunta por «el mes pasado».")
    res.update(motor=motor, via=via, plan=plan, aviso=aviso)
    if previo and not empieza_y and previo == plan and res.get("ok"):
        notas.append("Es la misma consulta que acabas de hacer; si buscas otra cosa, cambia el período, agrupa («por cliente») o filtra («solo MELI»).")
    if res.get("ok"):
        if res.get("tipo") not in ("alertas", "resumen", "sin_ventas"):
            res["texto"] = frase(res, plan, dim)
        res["seguir"] = seguimientos(res, plan, [qn_] + [memoria.normalizar(x) for x in (previas or [])])
        _explicar(q, res, notas)
    return res, ctx
