"""Conexión de solo lectura al SQL Server de las bases (plan de ventas, saldos).

Los datos de conexión salen de la pestaña Configuración de la plataforma, que los
guarda en la base local de cada persona. Si ahí no hay nada, se usa lo del archivo
.env, como antes. Sin usuario propio de SQL Server se entra con la cuenta de Windows.
La clave va aparte para no tener que escapar caracteres especiales en la URL.
"""
import threading

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from ..config import settings

CLAVE_CONFIG = "conexion_bases"
_guardada: dict = {}          # lo que el usuario dejó en Configuración


def usar_conexion(datos: dict) -> None:
    """Fija los datos de conexión de esta instalación (los carga la API al arrancar)."""
    global _guardada
    _guardada = dict(datos or {})
    _soltar_motor()
    limpiar_cache()


def conexion_actual() -> dict:
    return dict(_guardada)


def url_bases():
    servidor = (_guardada.get("url") or "").strip() or settings.bases_url
    usuario = (_guardada.get("usuario") or "").strip() or settings.bases_usuario
    clave = _guardada.get("clave") if _guardada.get("usuario") else settings.bases_clave
    if not servidor:
        raise RuntimeError("Falta la conexión a SQL Server: configúrala en Configuración.")
    url = make_url(servidor)
    if usuario:
        query = {k: v for k, v in url.query.items() if k.lower() != "trusted_connection"}
        url = url.set(username=usuario, password=clave or "", query=query)
    return url


def probar() -> dict:
    """Intenta conectarse y contar una tabla, para avisar si las credenciales sirven."""
    from sqlalchemy import text
    try:
        with motor_bases().connect() as cx:
            cx.execute(text("SELECT 1"))
        u = url_bases()
        return {"ok": True, "mensaje": f"Conectado a {u.host or u.database} "
                                       f"como {u.username or 'tu cuenta de Windows'}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "mensaje": str(e)[:300]}


_motor: tuple[str, Engine] | None = None
_candado_motor = threading.Lock()
ESPERA_CONEXION = 10     # segundos para entrar al servidor
ESPERA_CONSULTA = 60     # segundos máximos por consulta


def _soltar_motor() -> None:
    global _motor
    with _candado_motor:
        if _motor is not None:
            _motor[1].dispose()
        _motor = None


def motor_bases() -> Engine:
    """Un único motor para todas las consultas: antes se creaba uno nuevo (y sus conexiones)
    en cada consulta y quedaban abiertos. Se rehace solo si cambian los datos de conexión."""
    global _motor
    url = url_bases()
    huella = url.render_as_string(hide_password=False)
    with _candado_motor:
        if _motor is None or _motor[0] != huella:
            if _motor is not None:
                _motor[1].dispose()
            args = {"timeout": ESPERA_CONEXION} if url.drivername.startswith("mssql") else {}
            _motor = (huella, create_engine(url, pool_pre_ping=True, connect_args=args))
        return _motor[1]


# ---------------------------------------------------------------------------
# Consultas. El plan usa la MISMA consulta que el Excel ("Plan SOP"), para que
# ambos muestren los mismos números (incluye la regla CONSENSO / MARKET&SHARE).
# ---------------------------------------------------------------------------
import re
import time

_CACHE: dict[str, tuple[float, object]] = {}
CACHE_SEG = 600   # 10 minutos


_FALLOS: dict[str, tuple[float, Exception]] = {}
PAUSA_TRAS_FALLO = 60     # segundos sin volver a preguntar a un servidor que no respondió


def _cache(clave: str, fn):
    ahora = time.time()
    if clave in _CACHE and ahora - _CACHE[clave][0] < CACHE_SEG:
        return _CACHE[clave][1]
    if clave in _FALLOS and ahora - _FALLOS[clave][0] < PAUSA_TRAS_FALLO:
        raise _FALLOS[clave][1]                  # cada intento fallido costaba la espera completa de la conexión
    try:
        valor = fn()
    except Exception as e:  # noqa: BLE001
        _FALLOS[clave] = (ahora, e)
        raise
    _FALLOS.pop(clave, None)
    _CACHE[clave] = (ahora, valor)
    return valor


def limpiar_cache():
    _CACHE.clear()
    _FALLOS.clear()


def _sku(v) -> str:
    return re.sub(r"^0+(?=\d)", "", str(v or "").strip())


SQL_PLAN = """
SET NOCOUNT ON;
SET DATEFIRST 1;
DECLARE @DiaHabil INT;
DECLARE @TipoMesActual VARCHAR(20);

SELECT @DiaHabil = COUNT(*)
FROM (
    SELECT TOP (DAY(GETDATE()))
        DATEADD(DAY, ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1,
                DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AS Fecha
    FROM sys.objects
) t
WHERE DATEPART(WEEKDAY, Fecha) <= 5;

WITH Base AS (
    SELECT SOP, TIPO, AÑO, MES, CANAL, GRUPO_SOP, PRODUCT_ID, UNIDADES, ID, AÑO_PLAN, Fecha_Carga,
        ROW_NUMBER() OVER (PARTITION BY AÑO, MES, CANAL, GRUPO_SOP, PRODUCT_ID, TIPO
                           ORDER BY Fecha_Carga DESC, ID DESC) AS rn
    FROM [DP_S&OP_CICLO]
    WHERE AÑO = YEAR(GETDATE()) AND MES = MONTH(GETDATE())
      AND SOP = 'SOP' + RIGHT('0' + CAST(MONTH(GETDATE()) AS VARCHAR(2)), 2)
      AND AÑO_PLAN = YEAR(GETDATE())
),
ControlMesActual AS (
    SELECT MAX(CASE WHEN TIPO = 'MARKET&SHARE' AND rn = 1 THEN Fecha_Carga END) AS Fecha_MS,
           MAX(CASE WHEN TIPO = 'CONSENSO' AND rn = 1 THEN Fecha_Carga END) AS Fecha_Consenso
    FROM Base
)
SELECT @TipoMesActual =
    CASE WHEN @DiaHabil >= 5 THEN 'CONSENSO'
         WHEN Fecha_Consenso IS NULL THEN 'MARKET&SHARE'
         WHEN Fecha_Consenso > Fecha_MS THEN 'CONSENSO'
         ELSE 'MARKET&SHARE' END
FROM ControlMesActual;

WITH Base AS (
    SELECT TIPO, GRUPO_SOP, PRODUCT_ID, UNIDADES, ID, Fecha_Carga,
        ROW_NUMBER() OVER (PARTITION BY AÑO, MES, CANAL, GRUPO_SOP, PRODUCT_ID, TIPO
                           ORDER BY Fecha_Carga DESC, ID DESC) AS rn
    FROM [DP_S&OP_CICLO]
    WHERE AÑO = YEAR(GETDATE()) AND MES = MONTH(GETDATE())
      AND SOP = 'SOP' + RIGHT('0' + CAST(MONTH(GETDATE()) AS VARCHAR(2)), 2)
      AND AÑO_PLAN = YEAR(GETDATE())
      AND GRUPO_SOP = ?
),
Ventas AS (
    SELECT grupoSop, codigo, SUM(volReal) AS volReal, SUM(volPdteMes) AS volPdteMes
    FROM bi_performance_ventas
    WHERE grupoSop = ?
    GROUP BY grupoSop, codigo
)
SELECT b.TIPO, b.PRODUCT_ID, b.UNIDADES,
       ISNULL(v.volReal, 0) AS volReal, ISNULL(v.volPdteMes, 0) AS volPdteMes, b.Fecha_Carga
FROM Base b
LEFT JOIN Ventas v ON b.GRUPO_SOP = v.grupoSop AND b.PRODUCT_ID = v.codigo
WHERE b.TIPO = @TipoMesActual;
"""

SQL_DISPONIBILIDAD = """
SET NOCOUNT ON;
SELECT t.codigoSap, t.cantidad, t.fechaDisponibilidad
FROM (
    SELECT codigoSap, cantidad, fechaDisponibilidad,
           ROW_NUMBER() OVER (PARTITION BY codigoSap ORDER BY fechaDisponibilidad ASC) AS rn
    FROM od_disponibilidad_productos
) t
WHERE t.rn = 1;
"""


def _filas(sql: str, params: tuple = ()) -> list[tuple]:
    """Ejecuta un lote con varias instrucciones y devuelve el último resultado."""
    cx = motor_bases().raw_connection()
    try:
        directa = getattr(cx, "driver_connection", None)
        if directa is not None and hasattr(directa, "timeout"):
            directa.timeout = ESPERA_CONSULTA          # un servidor colgado no deja la plataforma esperando para siempre
        cur = cx.cursor()
        cur.execute(sql, params)
        while cur.description is None:
            if not cur.nextset():
                return []
        return [tuple(r) for r in cur.fetchall()]
    finally:
        cx.close()


def plan_sop(grupo: str) -> dict:
    """{sku: {plan, vendido, pdte_mes, tipo}} del mes actual para un grupo SOP."""
    def cargar():
        out = {}
        for tipo, sku, unidades, vendido, pdte, _fecha in _filas(SQL_PLAN, (grupo, grupo)):
            plan = float(unidades or 0)
            vendido, pdte = float(vendido or 0), float(pdte or 0)
            # El saldo NO se calcula aquí: la regla oficial es plan − real − en entrega,
            # y la "en entrega" viene de ZSD001_03 (ver app/analisis.py).
            out[_sku(sku)] = {"plan": plan, "vendido": vendido, "pdte_mes": pdte, "tipo": tipo}
        return out
    return _cache(f"plan:{grupo}", cargar)


def disponibilidad() -> dict:
    """{sku: {cantidad, fecha}}: primera disponibilidad por producto (igual que el Excel)."""
    def cargar():
        return {_sku(c): {"cantidad": int(q or 0), "fecha": f.isoformat() if f else ""}
                for c, q, f in _filas(SQL_DISPONIBILIDAD)}
    return _cache("disp", cargar)


SQL_CALEFONES = """
SET NOCOUNT ON;
SELECT codigoSap
FROM bi_maestra_producto
LEFT JOIN bi_distribucionLCM AS BDL ON BDL.clasificacion2 = clasifPdto2
WHERE clasifPdto2 = 'CALEFONT'
  AND mercado = 'DM'
  AND estado NOT IN ('Reemplazado', 'Eliminado')
  AND codigoEstado NOT IN ('01','Z1','Z6','Z7')
  AND estadoComercial NOT IN ('Sin Estado');
"""

SQL_PEDIDOS = """
SET NOCOUNT ON;
SELECT fechaCreacion, pedidoVenta, ordenCompra, fechaVencimiento
FROM bi_base_pedidos_sap
WHERE YEAR(fechaCreacion) = YEAR(GETDATE())
  AND canal = '1._  RETAIL'
ORDER BY fechaCreacion;
"""


def calefones() -> set[str]:
    """SKU clasificados como CALEFONT (la restricción de HITES)."""
    def cargar():
        return {_sku(c) for (c,) in _filas(SQL_CALEFONES) if c}
    return _cache("calefones", cargar)


def pedidos_ingresados() -> list[dict]:
    """Pedidos del año con su orden de compra, para buscar por cualquiera de los dos."""
    def cargar():
        return [{"fecha": f.isoformat() if hasattr(f, "isoformat") else str(f or ""),
                 "pedido": _sku(p), "oc": str(o or "").strip(),
                 "vence": v.isoformat() if hasattr(v, "isoformat") else str(v or "")}
                for f, p, o, v in _filas(SQL_PEDIDOS)]
    return _cache("pedidos", cargar)


def buscar_pedido(texto: str) -> list[dict]:
    """Busca por N° de pedido o por orden de compra (coincidencia exacta o parcial)."""
    t = str(texto or "").strip().upper()
    if not t:
        return []
    filas = pedidos_ingresados()
    exactos = [f for f in filas if _sku(f["pedido"]) == _sku(t) or f["oc"].upper() == t]
    if exactos:
        return exactos[:20]
    return [f for f in filas if t in f["pedido"] or t in f["oc"].upper()][:20]
