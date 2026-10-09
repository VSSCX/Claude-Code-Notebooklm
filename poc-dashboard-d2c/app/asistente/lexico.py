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
han habido nos ya entro entraron tan bien ido subieron bajaron balance panorama nuestros nuestro siguen usado usados pesos antes reparto alcanza puedes podrias puede decir duda consulta oye periodo listado incluyen incluye contienen llevan esperando debo revisar quien quienes como vamos van vas va vende venden compra compran poco pocos resumen evolucion tendencia sap vtex pasa algun alguno alguna distintos diferentes compraron tuvieron entrega entregas plazo ticket promedio promedios porcentaje tasa ratio vencido vencidos vencida atrasado atrasados alerta alertas""".split())

# conceptos de varias palabras o con terminaciones
P_AYUDA = r"\b(ayuda|ayudame|que puedes|que sabes|que se puede|que preguntas|que datos|como funciona|que haces|para que sirves)\b"
P_SALUDO = r"^\s*(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|saludos|gracias)\b"
P_INFO = r"hasta cuando|ultima actualizacion|ultima carga|datos actualizados|desde cuando|cuando fue el ultimo pedido|ultimo pedido|hay datos"
P_STOCK = r"\bstock\b|disponibilidad|disponible|inventario|existencias?|agot\w+|\bquedan?\b|cobertura|\bquebrar\w*|(?:cuant\w+\s+)?(?:hay|tenemos|tengo|quedan?)\s+(?:de|en bodega)\b|\bunidades en bodega"
P_ALERTAS = (r"anomali\w*|que (?:debo|tengo que|hay que) revisar|que reviso|que esta (?:mal|raro|fallando)|algo raro|\braro\b|\bproblemas?\b|"
             r"que (?:esta|estan) (?:en riesgo|critico\w*)|anormal\w*|\batender\b|\bprioridad\w*|\bprioritari\w*|\bcosas\s+(?:raras|urgentes|criticas)\b|\balertas?\b(?! (?:bws|mkp|post))|\bsemaforo\b|\burgente\w*")
P_LISTAR = r"\b(list\w*|muestr\w*|mostrar|dam?e|dime|indi\w+|detall\w*|cuales|enumer\w*|ver)\b"
P_CONTAR = r"\b(cuantos|cuantas|cuanto|total|cantidad|numero de)\b"
P_ENTIDAD_LISTA = r"\b(pedidos?|ordenes|orden|pvs?|lineas|productos)\b"

P_CANCELADO = r"\b(cancel\w*|anulad\w*|anulaci\w*|anular\w*)\b"
P_SIN_DESPACHO = r"factur\w* sin despach\w*|(?:alerta|atencion|boton|marcador)\s+integracion"
P_FACTURADO = r"\bfactur(?:ad|aron|amos|o\b|an\b|ar\b)\w*"
P_PENDIENTE = r"\b(pendiente\w*|por preparar|sin preparar|ready|listos? para (?:preparar|despach\w*)|sin despachar)\b"
P_NO_INTEGRADO = r"\bno\s+(?:(?:se|est\w*|han|ha|sido|fueron|fue|estan|esta)\s+)*(?:integrad|ingresad)\w*|\bsin\s+(?:pv|ingres\w*|integrar\w*|pedido sap)\b|\bpor integrar\b|\bno\s+(?:han\s+|ha\s+)?(?:llegado|pasado|subido|entrado)\s+a\s+(?:sap|pv)\b|\bsin\s+(?:llegar|pasar)\s+a\s+sap\b"
P_INTEGRADO = r"\b(?:integrad|ingresad)\w*"
P_VENCIDO = r"\b(vencid\w*|atrasad\w*|atrasos?|retrasad\w*|retrasos?|fuera de plazo|pas(?:o|aron|ada|adas|ados)\s+(?:de\s+)?(?:su\s+)?fecha)\b"
P_QUIEBRE = r"\bquiebres?\b|\bsin stock\b|falta de stock|stock insuficiente"

ALERTAS = {"alerta_bws": r"(?:alerta|atencion)\s+bws", "alerta_mkp": r"(?:alerta|atencion)\s+mkp",
           "alerta_post": r"(?:alerta|atencion)\s+(?:post|pos)(?:\s+fechado)?"}

P_METRICAS = [  # el orden manda: lo primero que calza gana
    ("distintos", r"\bcuantos\s+(?:clientes|canales|bodegas)\s+(?:\w+\s+){0,2}?(?:hicieron|hacen|hicimos|tuvieron|pidieron|ordenaron|con pedidos|compraron)\b|\b(?:cuantos|cuantas|numero de|cantidad de)\s+(?:\w+\s+)?(?:clientes|productos|skus?|canales|bodegas|modelos|articulos|clasificaciones|categorias)\s+(?:\w+\s+){0,2}?(?:distint\w*|diferentes|unic\w*|hay|tenemos|compraron|compran|vendimos|vendieron|se vendieron|han comprado|han vendido|vendidos|activos|con ventas)"),
    ("upp", r"(?:promedio|media)\s+de\s+unidades\s+por\s+pedido|unidades\s+(?:promedio\s+)?por\s+pedido|tamano (?:promedio )?(?:del|de) pedido"),
    ("pct_estado", r"(?:porcentaje|%|tasa|ratio|proporcion|indice)\s+(?:de\s+)?(?:pedidos\s+)?(?:cancel\w*|factur\w*|vencid\w*|atrasad\w*)|que\s+tanto\s+se\s+(?:cancela|anula|factura)\w*|cuanto\s+se\s+cancela"),
    ("pct_integracion", r"(?:que\s+porcentaje|porcentaje|que\s+tanto).{0,40}\bsap\b|(?:porcentaje|%|tasa|ratio|nivel).{0,30}(?:integra\w*|ingres\w*)|% integrad\w*"),
    ("pct_pendiente", r"(?:porcentaje|%|tasa|ratio).{0,30}pendiente\w*"),
    ("monto_riesgo", r"monto en riesgo|dinero en riesgo|plata en riesgo|(?:monto|plata|dinero|venta)s? (?:que )?(?:esta|estan) en riesgo|cuanto\s+(?:\w+\s+){0,2}?en riesgo|(?:plata|dinero|monto)\s+(?:\w+\s+){0,3}?en juego"),
    ("ticket", r"\bticket\b|(?:monto|valor|venta)s? promedio|promedio por pedido"),
    ("antiguedad", r"antiguedad|dias de atraso|cuantos dias llevan"),
    ("desfase", r"desfase|(?:cuanto|cuantos dias)\s+(?:se\s+)?(?:tarda|demora)\w*\s+(?:\w+\s+){0,3}?en\s+(?:integrar|ingresar)\w*|dias entre .{0,30}(?:creacion|crear|crea).{0,30}(?:ingres|integr)\w*|dias que (?:se )?(?:tarda|demora)\w*|demora\w*\s+(?:\w+\s+){0,3}?en\s+(?:pasar|llegar|subir|entrar|ingresar)\s+a\s+(?:sap|pv)|(?:cuanto|cuantos dias)\s+(?:se\s+)?(?:tarda|demora)\w*\s+en\s+(?:integrar|ingresar)\w*|dias en integrar\w*"),
    ("unidades", r"\b(unidad\w*|uds?|piezas?|qty|items?)\b|\bcuant[ao]s?\s+(?:equipos|piezas|items|artefactos|aparatos)\b"),
    ("monto", r"\bcuant[ao]\s+(?:plata|dinero)\b|\bcuanto\s+(?:se\s+|nos\s+)?(?:factur\w+|dejo|dejaron|compro|compraron|vendio|ingreso|entro|entraron|recaudamos|ganamos)\b|\btotal\s+(?:vendido|facturado)|\bvendid[oa]s?\s+por\b|\b(monto|montos|venta|ventas|facturacion|plata|dinero|valor|ingresos|importe|revenue)\b|\$|cuanto (?:se )?(?:vendio|vendimos|vendieron|facturamos|facturaron|llevamos)|\b(?:se\s+)?(?:vendio|vendieron|vendimos|compra|compran|compro)\b"),
    ("lineas", r"\blineas?\b"),
    ("pedidos", r"\b(pedidos?|ordenes|orden|pvs?)\b"),
]

DIMENSIONES = {"dia": "dia", "semana": "semana", "mes": "mes", "cliente": "cliente", "canal": "canal", "bodega": "bodega",
               "estado": "estado", "status": "status", "sla": "sla", "producto": "producto", "modelo": "producto",
               "sku": "producto", "articulo": "producto", "causa": "causa", "motivo": "causa",
               "clasificacion": "clasif2", "clasif2": "clasif2", "clasif": "clasif2", "categoria": "clasif2", "familia": "clasif2", "linea de producto": "clasif2",
               "tipo de producto": "clasif2", "tipo": "clasif2", "despacho": "sla", "tipo de despacho": "sla", "tipo de envio": "sla"}
P_POR_DIM = r"\b(?:por|segun|cada|agrupad\w* por|desglos\w* por|separad\w* por)\s+(dia|semana|mes|cliente|canal|bodega|estado|status|sla|producto|modelo|sku|articulo|causa|motivo|clasificacion|clasif2|clasif|categoria|familia|linea de producto|tipo de producto)(?:es|s)?\b"
P_CUAL_DIM = r"\b(?:que|cual|cuales|cuantos?)\s+(?:\w+\s+){0,2}?(cliente|canal|producto|modelo|bodega|dia|sla)s?\b.{0,40}\b(mas|menos|mayor|menor|mejor|peor)\b"
P_STATUS_DE = r"\b(status|estados?)\s+(?:de|del|de los|por)\b"
P_RANKING = r"mas vendid\w*|menos vendid\w*|ranking|\btop\s*\d*|mejores|peores"
P_ASC = r"\b(menos|menor\w*|peor\w*|minim\w*|ascendente)\b"
P_COMPARAR = r"\b(compar\w*|vs|versus|respecto (?:a|al|del|de la)|contra (?:la|el|ayer|el mes|la semana))\b"

# --- agrupaciones por ranking y cronologia
DIM_PAL = r"(dia|cliente|canal|bodega|producto|modelo|sla|mes|semana|clasificacion|categoria|familia|despacho|tipo de despacho|tipo de envio)(?:es|s)?"
P_SUPER_ANTES = r"\b(mejor|peor|mayor|menor|principal)(?:es)?\s+" + DIM_PAL + r"\b"
P_SUPER_DESPUES = r"\b" + DIM_PAL + r"\s+(?:\w+\s+){0,3}?(?:con|que|de)?\s*\b(mas|menos|mayor|menor)\b"
P_EVOLUCION = r"\b(evolucion|tendencia|historico|serie|curva)\b|\bdiari[ao]s?\b|\bdia a dia\b|\bpor dia\b"
P_MENSUAL = r"\bmensual(?:es)?\b|\bmes a mes\b|\bpor mes\b|\bcada mes\b"
P_SEMANAL = r"\bsemanal(?:es)?\b|\bsemana a semana\b|\bpor semana\b"

# --- pedidos grandes, montos y antiguedad
P_PEDIDO_GRANDE = r"\b(?:pedidos?|ordenes)\s+(?:mas\s+)?(?:grandes?|caros?|altos?|costosos?|valiosos?)\b|\b(?:mayor|menor)\s+(?:monto|valor)\b|\bmas\s+(?:caros?|grandes?|costosos?)\b|\bmas\s+(?:barato|chico|pequeno)s?\b"
P_MONTO_MIN = r"\b(?:mas|mayor(?:es)?|superior(?:es)?|sobre|encima)\s+(?:de|a|que|del)\s+\$?\s*(\d+)\s*(millones?|millon|mil|k|m)?\b"
P_MONTO_MAX = r"\b(?:menos|menor(?:es)?|inferior(?:es)?|bajo|debajo)\s+(?:de|a|que|del)\s+\$?\s*(\d+)\s*(millones?|millon|mil|k|m)?\b"
P_EDAD = r"\b(?:mas|mayor(?:es)?)\s+de\s+(\d{1,3})\s+dias?\b"

# --- acciones nuevas
P_RESUMEN = r"\bresumen\b|\bcomo\s+(?:vamos|estamos|andamos|va|nos va|nos fue)\b|\bpanorama\b|\bbalance\b|\bkpis?\b|\bindicadores\b|\bsituacion\b|\bestado general\b"
P_SIN_VENTAS = r"sin ventas|sin movimiento|no (?:se )?(?:han |ha )?(?:vendid\w*|vendio|vendieron|vende)|no tienen ventas|sin vender|sin rotacion"
P_FECHA_HOY = r"\bque\s+(?:dia|fecha)\s+(?:es|estamos)\b|\bfecha de hoy\b|\ba que fecha\b"
P_GRACIAS = r"^\s*(?:muchas\s+)?(?:gracias|grax|ok|okey|vale|perfecto|genial|excelente|buenisimo|listo|entendido|de acuerdo)\b[\s!.]*$"
P_CHAO = r"^\s*(?:chao|adios|hasta luego|nos vemos|bye)\b"
P_HORAS = r"\bultim[ao]s?\s+(?:\d+\s+)?horas?\b|\bpor hora\b|\bhora por hora\b"

# --- stock
P_STOCK_SIN = r"\bsin stock\b|\bno (?:tiene|tienen|tenemos|hay|queda|quedan|tienes) stock\b|\bfalta(?:n)? stock\b|\bagotad\w*|\bquebrad\w*|\bquiebre\b"
P_STOCK_POCO = r"\bpoco stock\b|\bse\s+(?:nos\s+)?(?:esta|estan)\s+(?:agotando|acabando|terminando)\b|\bagotando\b|\bacabando\b|\bstock bajo\b|\bbajo stock\b|\bpor acabarse\b|\bse (?:va|van) a (?:quebrar|acabar|agotar)\b|\bproximos? a quebrar\b|\bpor agotarse\b|\bcriticos?\b|\briesgo de quiebre\b|\bstock critico\b"
P_STOCK_COB = r"\bcobertura\b|\bdias de (?:inventario|stock)\b|\bcuantos dias (?:de stock|nos|le|alcanza\w*|dura\w*)\b|\bpara cuantos dias\b|\brotacion\b"
P_STOCK_TODO = r"\b(?:stock|inventario)\s+(?:\w+\s+){0,3}?en total\b|\ben total\b.{0,25}\b(?:stock|inventario)\b|\bcuanto\s+(?:stock|inventario)\b|\b(?:stock|inventario)\s+total\b|\btodo el (?:stock|inventario)\b|\bstock de todos\b|\binventario completo\b|\btodos los productos\b|\bstock completo\b"

# --- pedido: que se quiere saber de el
P_FOCO_PRODUCTOS = r"\b(?:productos?|articulos?|items?|detalle|contenido|que (?:compro|compraron|tiene|trae|lleva|contiene|incluye)|que hay en)\b"
P_FOCO_LINEAS = r"\bcuant[ao]s\s+(?:lineas?|productos?|items?|articulos?|unidades|piezas)\b|\bnumero de lineas\b"
P_FOCO_ESTADO = r"\b(?:estado|status|en que esta|donde esta|como va|integrado|facturado|cancelado|causa|motivo|por que esta)\b"

P_SIN_ACTIVIDAD = r"\b(clientes?|canales?|bodegas?|sla)\s+(?:que\s+)?(?:no|sin)\s+(?:ha\s+|han\s+|hay\s+|tuvo\s+|tuvieron\s+|tiene\s+|tienen\s+)?(?:comprado|compraron|compra|pedidos?|ventas?|movimiento|actividad)\b"
DOMINIO = r"pedido|orden|venta|stock|inventario|cliente|producto|bodega|canal|sla|monto|unidad|factur|cancel|integr|sap|vtex|entrega|despacho|status|estado|ticket|categoria|clasif|pendiente|atras|vencid|quiebre|linea|sku|modelo|refrigerador|lavadora|cocina|post|meli|falabella|ripley|paris|mademsa|electrolux|fensa"

P_PCT_TOTAL = r"\b(?:vs|versus|sobre|del|respecto (?:al|del)|en relacion (?:al|con el))\s+(?:el\s+)?total\b"

P_QUIEN_MAS = r"\bquien(?:es)?\s+(?:nos\s+)?(?:compra|compran|vende|factura|pide|piden)\w*\s+mas\b|\bquien(?:es)?\s+(?:es|son)\s+(?:nuestro|nuestros)\s+(?:mejor|mejores)\s+clientes?\b"
P_LO_MAS_VENDIDO = r"\b(?:que\s+)?(?:es\s+)?lo\s+que\s+(mas|menos)\s+se\s+vende\b|\bque\s+se\s+vende\s+(mas|menos)\b|\bproductos?\s+estrella\b|\bbest\s*sellers?\b|\bcasi\s+no\s+se\s+vend\w+\b|\bpoco\s+vendid\w+\b|\blo\s+mas\s+vendido\b"
