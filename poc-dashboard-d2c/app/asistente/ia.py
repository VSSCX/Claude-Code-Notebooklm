"""IA opcional: traduce la pregunta a un plan (JSON). La IA nunca ve los pedidos ni escribe SQL; el servidor calcula la cifra.

Modos (IA_MODO en el .env): ollama | openai (cualquier servidor compatible: LM Studio, vLLM, llama.cpp...) | anthropic (SDK oficial `anthropic`).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

import pandas as pd

from app.config import settings

from . import esquema as E

MODELO_ANTHROPIC = "claude-opus-5-5"


def info_motor() -> dict:
    m = settings.ia_modo
    if m not in ("ollama", "openai", "anthropic"):
        return {"modo": "reglas", "nombre": "Reglas (sin IA)", "modelo": None, "local": True}
    url = settings.ia_url or ("https://api.anthropic.com" if m == "anthropic" else "http://localhost:11434")
    local = bool(re.match(r"https?://(localhost|127\.|\[::1\])", url))
    modelo = settings.ia_modelo or (MODELO_ANTHROPIC if m == "anthropic" else "")
    return {"modo": m, "nombre": ("IA local" if local else "IA externa") + (f" ({modelo})" if modelo else ""), "modelo": modelo, "local": local}


# JSON Schema del plan, para los servidores que fuerzan la estructura (Anthropic: output_config.format)
SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "accion": {"type": "string", "enum": list(E.ACCIONES)}, "metrica": {"type": "string", "enum": list(E.METRICAS)},
    "producto": {"type": "string"}, "sku": {"type": "string"}, "pedido": {"type": "string"},
    "periodo": {"type": "string", "enum": list(E.PERIODOS)}, "dias": {"type": "integer"},
    "desde": {"type": "string"}, "hasta": {"type": "string"},
    "canal": {"type": "array", "items": {"type": "string"}}, "cliente": {"type": "array", "items": {"type": "string"}},
    "bodega": {"type": "array", "items": {"type": "string"}}, "sla": {"type": "array", "items": {"type": "string"}},
    "estado": {"type": "array", "items": {"type": "string", "enum": list(E.ESTADOS)}},
    "agrupar": {"type": "string", "enum": list(E.AGRUPAR)}, "orden": {"type": "string", "enum": ["asc", "desc"]},
    "top": {"type": "integer"}, "comparar": {"type": "boolean"}}}


def prompt_sistema(K: dict, hoy: pd.Timestamp, ejemplos: list | None = None) -> str:
    j = lambda x: json.dumps(x, ensure_ascii=False)  # noqa: E731
    return f"""Eres el traductor de preguntas de un dashboard de pedidos D2C (VTEX contra SAP). NO respondas la pregunta ni inventes cifras:
devuelve SOLO un objeto JSON con los campos que apliquen (omite los que no).
Hoy es {hoy.strftime('%Y-%m-%d')}.
Campos:
- accion: medir (cifra o desglose), listar (lista de pedidos con sus productos), pedido (un pedido por su numero), stock, ayuda, info (hasta cuando hay datos).
- metrica: unidades | pedidos | monto (ventas) | lineas | ticket | pct_integracion | pct_pendiente | antiguedad | desfase (dias entre crear en VTEX e ingresar a SAP) | monto_riesgo.
- producto: nombre o modelo del producto tal como lo dijo el usuario (por ejemplo "med165b" o "lavadora 8,5 kg"). sku: codigo SAP de 9 digitos. pedido: numero de pedido (Sequence) o de pedido SAP.
- periodo: hoy | ayer | semana | semana_anterior | mes (mes en curso) | mes_anterior | ultimos (con dias) | todo | rango (con desde y hasta AAAA-MM-DD). Si no dice el periodo usa mes.
- canal (subconjunto de {j(K['canal'])}), cliente ({j(K['cliente'])}), bodega ({j(K['bodega'])}; "post fechado" es POST_Fechado), sla ({j(K['sla'])}).
- estado (lista): no_integrado, integrado, cancelado (status canceled), pendiente (ready-for-handling), facturado (invoiced), vencido (entrega vencida), sin_despacho (facturado en SAP y pendiente en VTEX), alerta_bws, alerta_post, alerta_mkp, quiebre (pendiente por falta de stock).
- agrupar: dia | semana | mes | cliente | canal | bodega | estado | status | sla | producto | causa. orden: asc | desc. top: cuantas filas. comparar: true si pide comparar con el periodo anterior.
Reglas: con producto y sin metrica usa unidades. "venta(s)" es monto. "status de X" es agrupar por status. "el ultimo mes" son los ultimos 30 dias. "Mercado Libre" es el cliente MELI.
Ejemplos:
"cual es la venta de los ultimos 7 dias del med165b" -> {{"accion":"medir","metrica":"monto","producto":"med165b","periodo":"ultimos","dias":7}}
"cuantos pedidos se cancelaron el ultimo mes" -> {{"accion":"medir","metrica":"pedidos","estado":["cancelado"],"periodo":"ultimos","dias":30}}
"muestrame los pedidos post fechados de hoy con productos y monto" -> {{"accion":"listar","bodega":["POST_Fechado"],"periodo":"hoy"}}
"cual es el status de post fechado hoy" -> {{"accion":"medir","metrica":"pedidos","bodega":["POST_Fechado"],"periodo":"hoy","agrupar":"status"}}
"hay stock de la lavadora de 8,5 kg" -> {{"accion":"stock","producto":"lavadora 8,5 kg"}}""" + _validados(ejemplos)


def _validados(ejemplos) -> str:
    """Preguntas parecidas que los analistas ya validaron (pulgar arriba): la IA aprende de ellas en cada pregunta."""
    if not ejemplos:
        return ""
    lineas = [f'"{e["q"]}" -> {json.dumps({k: v for k, v in e["plan"].items() if v not in (None, [], False)}, ensure_ascii=False)}' for e in ejemplos]
    return "\nEjemplos validados por los analistas (misma forma, parecidos a la pregunta):\n" + "\n".join(lineas)


def _post(url: str, cuerpo: dict, cab: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST", headers={"Content-Type": "application/json", **cab})
    with urllib.request.urlopen(req, timeout=settings.ia_timeout) as r:   # noqa: S310  (la URL la fija quien administra el .env)
        return json.loads(r.read().decode("utf-8"))


def _anthropic(system: str, user: str) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("Falta instalar el paquete: pip install anthropic") from e
    modelo = settings.ia_modelo or MODELO_ANTHROPIC
    cli = anthropic.Anthropic(api_key=settings.ia_clave or None, base_url=settings.ia_url or None,
                              timeout=settings.ia_timeout, max_retries=1)
    cfg: dict = {"format": {"type": "json_schema", "schema": SCHEMA}}
    if modelo.startswith(("claude-opus-5", "claude-sonnet-5", "claude-fable", "claude-opus-4")):
        cfg["effort"] = "low"                               # traducir una frase corta no necesita razonar mucho
    base = dict(model=modelo, max_tokens=4000, system=system, messages=[{"role": "user", "content": user}])
    try:
        resp = cli.messages.create(**base, output_config=cfg)
    except anthropic.BadRequestError:                       # un modelo que no acepta esquema o esfuerzo: se pide solo con el prompt
        resp = cli.messages.create(**base)
    return "".join(b.text for b in resp.content if b.type == "text")


def _llm(system: str, user: str) -> str:
    modo, url, modelo = settings.ia_modo, (settings.ia_url or "").rstrip("/"), settings.ia_modelo
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if modo == "ollama":
        j = _post((url or "http://localhost:11434") + "/api/chat",
                  {"model": modelo or "qwen2.5:7b", "stream": False, "format": "json", "options": {"temperature": 0}, "messages": msgs}, {})
        return j["message"]["content"]
    if modo == "openai":
        cab = {"Authorization": "Bearer " + settings.ia_clave} if settings.ia_clave else {}
        cuerpo = {"model": modelo or "local", "temperature": 0, "messages": msgs}
        u = (url or "http://localhost:1234/v1") + "/chat/completions"
        try:
            j = _post(u, {**cuerpo, "response_format": {"type": "json_object"}}, cab)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 422):
                raise
            j = _post(u, cuerpo, cab)                       # servidores sin modo JSON
        return j["choices"][0]["message"]["content"]
    if modo == "anthropic":
        return _anthropic(system, user)
    raise RuntimeError("IA no configurada")


def planificar(q: str, K: dict, hoy: pd.Timestamp, previo: dict | None, ejemplos: list | None = None) -> dict | None:
    usuario = q if not previo else f"(plan de la pregunta anterior: {json.dumps(previo, ensure_ascii=False)})\n{q}"
    txt = _llm(prompt_sistema(K, hoy, ejemplos), usuario)
    m = re.search(r"\{.*\}", txt, re.S)
    return E.validar(json.loads(m.group(0)), K) if m else None
