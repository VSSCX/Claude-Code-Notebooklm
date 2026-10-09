"""Capa semantica del asistente: que se puede preguntar y como se valida un plan.

Un plan es un diccionario con campos fijos. Lo arman las reglas o una IA, y SIEMPRE pasa por `validar`: cada campo
se compara con listas permitidas y con los valores reales de la base (canales, clientes, bodegas, SLA). Lo demas se descarta.
"""
from __future__ import annotations

import re

import pandas as pd

from .texto import sa

ACCIONES = ("medir", "listar", "pedido", "stock", "alertas", "resumen", "sin_ventas", "ayuda", "info")
METRICAS = ("unidades", "pedidos", "monto", "lineas", "ticket", "pct_integracion", "pct_pendiente", "antiguedad", "monto_riesgo", "desfase", "distintos", "upp", "pct_estado")
PERIODOS = ("hoy", "ayer", "semana", "semana_anterior", "mes", "mes_anterior", "ultimos", "todo", "rango")
# estado = filtros sobre el estado del pedido (los mismos conceptos del tablero)
ESTADOS = ("no_integrado", "integrado", "cancelado", "pendiente", "facturado", "vencido", "sin_despacho",
           "alerta_bws", "alerta_post", "alerta_mkp", "quiebre")
AGRUPAR = ("dia", "semana", "mes", "cliente", "canal", "bodega", "estado", "status", "sla", "producto", "causa", "clasif2")
STOCK_MODOS = ("sin", "poco", "cobertura", "todo")
FOCOS = ("productos", "lineas", "estado")
LISTAS = ("canal", "cliente", "bodega", "sla")

ALIAS_CLIENTE = {"mercadolibre": "MELI", "mercado libre": "MELI"}
ALIAS_BODEGA = {"post": "POST_Fechado", "pos": "POST_Fechado", "postfechado": "POST_Fechado", "post fechado": "POST_Fechado",
                "pos fechado": "POST_Fechado", "post_fechado": "POST_Fechado"}


def plan_vacio() -> dict:
    return {"accion": None, "metrica": None, "producto": None, "sku": None, "pedido": None, "periodo": None, "dias": None,
            "desde": None, "hasta": None, "canal": [], "cliente": [], "bodega": [], "sla": [], "estado": [],
            "agrupar": None, "orden": None, "top": None, "comparar": False,
            "monto_min": None, "monto_max": None, "edad_min": None, "stock_modo": None, "foco": None}


def conocidos(dim: pd.DataFrame) -> dict:
    u = lambda c: sorted(str(x) for x in dim[c].dropna().unique())  # noqa: E731
    return {"cliente": u("SalesChannelName"), "canal": u("Canal"), "bodega": u("warehouse"), "sla": u("SLA_Type")}


def _fecha(v):
    try:
        return pd.Timestamp(v).strftime("%Y-%m-%d") if v else None
    except (ValueError, TypeError):
        return None


def _cadena(v, n=80):
    if isinstance(v, (str, int)) and str(v).strip():
        return re.sub(r"\s+", " ", str(v)).strip()[:n]
    return None


def _digitos(v):
    return (re.sub(r"\D", "", str(v))[:14] or None) if v not in (None, "") else None


def validar(p, K: dict) -> dict:
    """Limpia un plan venga de donde venga. Nunca falla: lo invalido queda en su valor vacio."""
    p = p if isinstance(p, dict) else {}
    out = plan_vacio()
    for k, validos in (("accion", ACCIONES), ("metrica", METRICAS), ("periodo", PERIODOS), ("agrupar", AGRUPAR)):
        out[k] = p.get(k) if p.get(k) in validos else None
    out["orden"] = p.get("orden") if p.get("orden") in ("asc", "desc") else None
    out["producto"] = _cadena(p.get("producto"))
    out["sku"], out["pedido"] = _digitos(p.get("sku")), _digitos(p.get("pedido"))
    out["desde"], out["hasta"] = _fecha(p.get("desde")), _fecha(p.get("hasta"))
    for k, lo, hi in (("dias", 1, 400), ("top", 1, 300)):
        try:
            out[k] = max(lo, min(int(p.get(k)), hi)) if p.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            out[k] = None
    out["comparar"] = p.get("comparar") is True
    out["stock_modo"] = p.get("stock_modo") if p.get("stock_modo") in STOCK_MODOS else None
    out["foco"] = p.get("foco") if p.get("foco") in FOCOS else None
    for k in ("monto_min", "monto_max"):
        try:
            v = float(p.get(k)) if p.get(k) not in (None, "") else None
            out[k] = v if v is not None and 0 <= v < 1e13 else None
        except (TypeError, ValueError):
            out[k] = None
    try:
        out["edad_min"] = max(1, min(int(p.get("edad_min")), 1000)) if p.get("edad_min") not in (None, "") else None
    except (TypeError, ValueError):
        out["edad_min"] = None
    if out["periodo"] == "rango" and not (out["desde"] or out["hasta"]):
        out["periodo"] = None
    if out["periodo"] == "ultimos" and not out["dias"]:
        out["periodo"] = None
    for k in LISTAS:
        v = p.get(k) or []
        v = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
        validos = {sa(x): x for x in K[k]}
        lista = []
        for x in v:
            clave = sa(x)
            if k == "cliente":
                clave = sa(ALIAS_CLIENTE.get(clave, x))
            elif k == "bodega":
                clave = sa(ALIAS_BODEGA.get(clave, x))
            y = validos.get(clave)
            if y and y not in lista:
                lista.append(y)
        out[k] = lista
    v = p.get("estado") or []
    v = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
    out["estado"] = [x for x in dict.fromkeys(v) if x in ESTADOS]
    return out
