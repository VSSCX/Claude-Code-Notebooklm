"""Vocabulario en espanol: palabras que no son productos y patrones de cada concepto (ya sin acentos ni mayusculas)."""
import re

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
         "octubre", "noviembre", "diciembre"]
NUM_MES = {n: i + 1 for i, n in enumerate(MESES[:9])} | {"setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}

# palabras corrientes: nunca son parte del nombre de un producto
STOP = set("""a al algo ante aqui ayer cada caer cayeron cayo caen cuantas cuantos cuanto cuanta cuales cual de del dia dias
dame dime el ella ellos en entraron entre es esa ese eso esta este estan fue fueron ha han hasta hay hoy la las le lo los
mes meses me mi mis muestrame muestra necesito no o para pasado pasada por porfa porfavor que quiero se semana semanas ser si sin sobre son su sus
tengo tenemos todo todos todas un una unas unos y vendimos vendieron vendido vendidas vendidos vendio venta ventas vender
unidad unidades uds ud pieza piezas pedido pedidos orden ordenes pv pvs monto montos total totales linea lineas canal canales
cliente clientes bodega bodegas ingresaron ingreso ingresos llegaron llego anterior ultimo ultimos ultima ultimas
saber ver busca buscar top mas menos mejor mejores peor peores comparado con desde durante mismo misma modelo modelos producto productos
equipo equipos quienes hubo tuvimos tuvo salieron salio generaron pendiente pendientes integrado integrados
integrada integradas cancelado cancelados cancelada canceladas cancelaron facturado facturados facturada facturadas facturaron
ranking agrupado agrupados agrupa detalle valor plata dinero aproximadamente actual actuales ahora indique indiquen indica
indicame lista listar listame dar dame muestren muestre estado status estados sla segun ordenados ordenado favor porfa
dinos gracias hola buenas stock disponible disponibles cuenta cuentan tiene tienen tenga estan estaba estamos esta hay habia
han habido algun alguno alguna distintos diferentes compraron tuvieron entrega entregas plazo ticket promedio promedios porcentaje tasa ratio vencido vencidos vencida atrasado atrasados alerta alertas""".split())

# conceptos de varias palabras o con terminaciones
P_AYUDA = r"\b(ayuda|ayudame|que puedes|que sabes|que se puede|que preguntas|que datos|como funciona|que haces|para que sirves)\b"
P_SALUDO = r"^\s*(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|saludos|gracias)\b"
P_INFO = r"hasta cuando|ultima actualizacion|ultima carga|datos actualizados|desde cuando|cuando fue el ultimo pedido|ultimo pedido|hay datos"
P_STOCK = r"\bstock\b|disponibilidad|disponible|inventario|existencias?|agotad\w*|\bquedan?\b|cobertura|(?:cuant\w+\s+)?(?:hay|tenemos|tengo|quedan?)\s+(?:de|en bodega)\b|\bunidades en bodega"
P_ALERTAS = (r"anomali\w*|que (?:debo|tengo que|hay que) revisar|que reviso|que esta (?:mal|raro|fallando)|algo raro|situacion (?:actual|de hoy)|"
             r"resumen (?:del dia|de hoy|ejecutivo)|como (?:vamos|estamos|andamos)|se (?:va|van) a quebrar|riesgo de quiebre|proyeccion de stock|"
             r"que (?:esta|estan) (?:en riesgo|critico\w*)|\balertas?\b(?! (?:bws|mkp|post))|problemas")
P_LISTAR = r"\b(list\w*|muestr\w*|mostrar|dam?e|dime|indi\w+|detall\w*|cuales|enumer\w*|ver)\b"
P_CONTAR = r"\b(cuantos|cuantas|cuanto|total|cantidad|numero de)\b"
P_ENTIDAD_LISTA = r"\b(pedidos?|ordenes|orden|pvs?|lineas|productos)\b"

P_CANCELADO = r"\b(cancel\w*|anulad\w*|anulaci\w*|anular\w*)\b"
P_SIN_DESPACHO = r"factur\w* sin despach\w*|(?:alerta|atencion|boton|marcador)\s+integracion"
P_FACTURADO = r"\bfactur(?:ad|aron|amos|ar\b)\w*"
P_PENDIENTE = r"\b(pendiente\w*|por preparar|sin preparar|ready|listos? para (?:preparar|despach\w*)|sin despachar)\b"
P_NO_INTEGRADO = r"\bno\s+(?:se\s+)?(?:han\s+)?(?:integrad|ingresad)\w*|\bsin\s+(?:pv|ingres\w*|integrar\w*|pedido sap)\b"
P_INTEGRADO = r"\b(?:integrad|ingresad)\w*"
P_VENCIDO = r"\b(vencid\w*|atrasad\w*|retrasad\w*|fuera de plazo)\b"
P_QUIEBRE = r"\bquiebres?\b|\bsin stock\b|falta de stock|stock insuficiente"

ALERTAS = {"alerta_bws": r"(?:alerta|atencion)\s+bws", "alerta_mkp": r"(?:alerta|atencion)\s+mkp",
           "alerta_post": r"(?:alerta|atencion)\s+(?:post|pos)(?:\s+fechado)?"}

P_METRICAS = [  # el orden manda: lo primero que calza gana
    ("pct_integracion", r"(?:porcentaje|%|tasa|ratio|nivel).{0,30}(?:integra\w*|ingres\w*)|% integrad\w*"),
    ("pct_pendiente", r"(?:porcentaje|%|tasa|ratio).{0,30}pendiente\w*"),
    ("monto_riesgo", r"monto en riesgo|dinero en riesgo|plata en riesgo"),
    ("ticket", r"\bticket\b|(?:monto|valor|venta)s? promedio|promedio por pedido"),
    ("antiguedad", r"antiguedad|dias de atraso|cuantos dias llevan"),
    ("desfase", r"desfase|(?:cuanto|cuantos dias)\s+(?:se\s+)?(?:tarda|demora)\w*\s+en\s+(?:integrar|ingresar)\w*|dias en integrar\w*"),
    ("unidades", r"\b(unidad\w*|uds?|piezas?|qty|items?)\b"),
    ("monto", r"\b(monto|montos|venta|ventas|facturacion|plata|dinero|valor|ingresos|importe|revenue)\b|\$|cuanto (?:se )?(?:vendio|vendimos|vendieron|facturamos|facturaron|llevamos)"),
    ("lineas", r"\blineas?\b"),
    ("pedidos", r"\b(pedidos?|ordenes|orden|pvs?)\b"),
]

DIMENSIONES = {"dia": "dia", "semana": "semana", "mes": "mes", "cliente": "cliente", "canal": "canal", "bodega": "bodega",
               "estado": "estado", "status": "status", "sla": "sla", "producto": "producto", "modelo": "producto",
               "sku": "producto", "articulo": "producto", "causa": "causa", "motivo": "causa"}
P_POR_DIM = r"\b(?:por|segun|cada|agrupad\w* por|desglos\w* por|separad\w* por)\s+(dia|semana|mes|cliente|canal|bodega|estado|status|sla|producto|modelo|sku|articulo|causa|motivo)s?\b"
P_CUAL_DIM = r"\b(?:que|cual|cuales|cuantos?)\s+(?:\w+\s+){0,2}?(cliente|canal|producto|modelo|bodega|dia|sla)s?\b.{0,40}\b(mas|menos|mayor|menor|mejor|peor)\b"
P_STATUS_DE = r"\b(status|estados?)\s+(?:de|del|de los|por)\b"
P_RANKING = r"mas vendid\w*|menos vendid\w*|ranking|\btop\s*\d*|mejores|peores"
P_ASC = r"\b(menos|menor\w*|peor\w*|minim\w*|ascendente)\b"
P_COMPARAR = r"\b(compar\w*|vs|versus|respecto (?:a|al|del|de la)|contra (?:la|el|ayer|el mes|la semana))\b"
