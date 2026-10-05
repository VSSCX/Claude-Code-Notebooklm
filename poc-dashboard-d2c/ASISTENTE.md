# Asistente de consultas (el chat del icono de arriba)

Pregunta en español, con tus palabras. Responde con cifras calculadas por el servidor sobre los datos ya cargados (VTEX, SAP y stock).

## Qué puede responder

| Tipo | Ejemplos |
|---|---|
| Ventas y unidades de un producto | «¿Cuál es la venta de los últimos 7 días del MED165B?» · «unidades de la lavadora 8,5 kg hoy» · «ventas del sku 910016501 ayer» |
| Pedidos por estado o status | «¿Cuántos pedidos se cancelaron el último mes?» · «pedidos facturados hoy» · «pedidos sin integrar de Falabella» · «pedidos pendientes con entrega vencida» · «pedidos con quiebre de stock» |
| Una bodega o un cliente | «¿Cuál es el status de POST Fechado hoy?» · «pedidos de Falabella en POST Fechado esta semana» · «ventas por bodega ayer» |
| Listados con detalle | «Que me indique los pedidos POST Fechado de hoy, productos, qty y monto» (tabla con pedido, producto, cantidad, monto, código SAP, status, cliente y fecha; el número de pedido abre su detalle; se descarga en CSV) |
| Rankings | «Top 5 clientes por monto este mes» · «qué cliente compró más» · «cuál fue el día con más pedidos» · «los 3 productos más vendidos hoy» |
| Comparaciones | «compara las ventas de esta semana con la anterior» |
| Indicadores del tablero | «porcentaje de integración por cliente» · «antigüedad promedio de los pendientes» · «monto en riesgo por canal» · «ticket promedio de MELI» |
| Stock | «¿hay stock del MED165B?» · «¿qué productos están sin stock?» (stock disponible = VTEX − Reservado, con las unidades que hay en pedidos pendientes) |
| Un pedido | «pedido 3506611» o su número SAP: estado, cliente, bodega, fechas, causa de pendiente y líneas |
| Seguimientos | después de una respuesta: «¿y ayer?», «¿y de MELI?», «por día», «ver los pedidos» (hereda lo que no cambias) |
| Datos y ayuda | «¿hasta cuándo hay datos?» · «¿qué puedes hacer?» |

Períodos: hoy, ayer, anteayer, hace N días, esta semana, semana pasada, este mes, mes pasado, últimos N días/semanas/meses, «el último mes»
(= últimos 30 días, y lo dice), un mes por nombre, una fecha o un rango (05-08 al 08-08). Si no dices el período usa el mes en curso.
No cuenta pedidos cancelados salvo que preguntes por ellos o pidas el desglose por status, y lo avisa en la respuesta.

**Reconoce productos como los escribes:** `med165b` es «MED 165B», `lavadoras` es «Lavadora…», `8,5 kg` calza con «8,5 kg», y corrige errores de
tipeo («refrigeradro»). Si pides varios productos parecidos (las dos variantes del MED 165B) los suma y los desglosa. Si el código de modelo no existe
(`xyz999`) lo dice y sugiere los más parecidos, en vez de contestar con otro producto.

**Lo que no sabe:** costos, márgenes, datos de clientes finales, direcciones, ni nada que no esté en las bases que lee el tablero. Si no entiende una
pregunta, lo dice y muestra ejemplos; no inventa.

## Memoria: aprende de las preguntas

Cada pregunta queda en un historial compartido por todos los analistas (`data/historial_asistente.jsonl`, solo el texto de la pregunta y su plan; nunca
las respuestas ni quién preguntó; en Vercel vive en memoria). Cada respuesta tiene un pulgar arriba y uno abajo («¿Te sirvió?»), y con eso:

- **Pulgar arriba:** la pregunta queda validada. Si alguien la repite, se usa su plan al instante (con los datos de ahora); si una pregunta nueva no se
  entiende pero se parece a una validada, se interpreta como esa y lo avisa; las palabras sueltas de preguntas validadas se dejan de avisar como «no usé».
- **Pulgar abajo:** si la misma pregunta se repite, avisa que la última vez no sirvió y sugiere reformular.
- **Con IA:** las preguntas parecidas ya validadas se envían como ejemplos en cada petición, así la IA aprende de lo que a ustedes les sirve.
- **Sugerencias:** el chat vacío muestra «Lo que más se pregunta» y el cuadro de texto autocompleta con el historial.
- **Para quien mantiene el programa:** `http://servidor:8000/api/chat/historial` lista cuánto se usa, qué porcentaje se entiende y las preguntas que **no** se
  entendieron o se marcaron como no útiles: ahí se ve qué reglas agregar. Los seguimientos («¿y ayer?») no se guardan como reutilizables porque dependen del
  contexto.

## Cómo funciona (y por qué es seguro)

```
pregunta ──► PLAN (JSON de campos fijos) ──► VALIDACIÓN (listas permitidas) ──► CÁLCULO (pandas, en el servidor)
             reglas en español, o una IA                                          cifra + desglose + tabla
```

Es una capa semántica: el plan nombra medidas (unidades, pedidos, monto, líneas, ticket, % integración...), filtros (período, canal, cliente, bodega,
SLA, estado, producto) y desgloses (día, cliente, bodega, status, producto...). Las reglas y la IA producen el mismo plan, y SIEMPRE pasa por la validación:
cada campo se compara con listas permitidas y con los valores reales (clientes, bodegas, SLA). Lo que no calza se descarta. El cálculo usa los datos que el
servidor ya tiene en memoria; nunca se ejecuta SQL ni código escrito por una IA. Aunque la IA se equivoque o alguien intente engañarla con el texto de la
pregunta, lo peor que pasa es que la pregunta se interprete mal.

Código: `app/asistente/` (`reglas.py` lenguaje, `esquema.py` plan y validación, `catalogo.py` productos, `consulta.py` cálculo, `redactar.py` respuestas,
`ia.py` modelos opcionales, `memoria.py` historial y aprendizaje, `motor.py` orquesta).

**Privacidad.** Con IA, al modelo solo se le envía el texto de la pregunta, la fecha de hoy y los nombres de canales, clientes, bodegas y SLA. Nunca pedidos,
montos ni productos. Con un modelo externo ese texto sale de tu red: la cabecera del chat dice «IA local» o «IA externa». Tope: 40 preguntas por minuto.

## Activar una IA (opcional)

Sin configurar funciona con reglas, sin IA ni internet. Para que entienda frases más libres, en el `.env` del equipo servidor y reiniciando `servidor.bat`:

| Quiero usar | `.env` |
|---|---|
| Ollama en el mismo equipo (local) | `IA_MODO=ollama` `IA_URL=http://localhost:11434` `IA_MODELO=qwen2.5:7b` |
| LM Studio, vLLM, llama.cpp u otro servidor compatible con OpenAI | `IA_MODO=openai` `IA_URL=http://localhost:1234/v1` `IA_MODELO=<modelo>` |
| Claude (Anthropic), con el SDK oficial | `pip install anthropic` y `IA_MODO=anthropic` `IA_CLAVE=<tu clave>` `IA_MODELO=claude-opus-5-5` |

Con Claude, si no indicas `IA_MODELO` usa `claude-opus-5-5` con esfuerzo bajo (traducir una frase corta no necesita razonar mucho). Para gastar menos puedes
fijar un modelo más pequeño en `IA_MODELO`; si el modelo no acepta el esquema o el esfuerzo, el asistente reintenta solo con el prompt. Para Ollama:
`ollama pull qwen2.5:7b`; un modelo de 7 a 8 mil millones de parámetros alcanza porque solo traduce frases cortas a un JSON pequeño. Si la IA tarda más de
`IA_TIMEOUT_SEGUNDOS` (25), falla o no devuelve un plan válido, el asistente responde igual con las reglas y lo avisa en una nota.

## Qué repositorios y agentes se revisaron

La idea inicial era usar un agente «texto a SQL / pandas» ya hecho. Se revisaron estos y se decidió **no** incrustarlos, aprovechando su idea central
(una capa semántica entre la pregunta y los datos: [Cube](https://cube.dev/articles/semantic-layer-for-ai-agents-2026), [Wren AI](https://www.getwren.ai/post/wren-ai-vs-vanna-the-enterprise-guide-to-choosing-a-text-to-sql-solution)):

| Proyecto | Qué hace | Por qué no se usó directamente |
|---|---|---|
| [Vanna](https://vanna.ai/) (MIT; el repositorio original se archivó en marzo de 2026) | Genera SQL con un LLM más RAG sobre tu esquema | La IA escribiría SQL contra la base de pedidos publicada a toda la red |
| [PandasAI](https://docs.pandas-ai.com/) | Convierte preguntas en código Python/SQL y lo ejecuta (con sandbox Docker) | Ejecuta código generado: exige aislamiento y más dependencias en un PC de empresa |
| [LangChain SQL / pandas agents](https://python.langchain.com/) | Agente que explora la base y escribe consultas | Dependencia grande y consultas generadas |
| [Wren AI](https://www.getwren.ai/) / [Cube](https://cube.dev/) | Capa semántica (medidas y dimensiones definidas) con una IA encima | Es la idea que sí se usó, pero como plan validado dentro de este programa, sin un servicio aparte |
| [DB-GPT-Hub](https://github.com/eosphoros-ai/db-gpt-hub) y [Awesome-Text2SQL](https://github.com/eosphoros-ai/Awesome-Text2SQL) | Modelos afinados y benchmarks de texto a SQL | Útiles solo si algún día se quiere SQL libre |
| [Ollama](https://ollama.com/) | Servidor local de modelos con salida JSON | **Soportado** como motor opcional |

## Cómo se probó y qué falta

`python probar_asistente.py` hace 39 comprobaciones con los datos de ejemplo (preguntas, ventas por Clasif2, memoria) y compara cada respuesta con una cifra calculada a mano con pandas (no con el código
del asistente): ventas y unidades del MED165B, cancelados del último mes, facturados, pendientes, POST Fechado (status y lista con productos, cantidad y monto),
rankings, comparación, ticket, stock, pedido por número SAP, ayuda, y preguntas que no entiende. Además se probaron unas 40 frases distintas (sinónimos, errores de
tipeo, «mercado libre», «anularon»...) y los tres modos de IA contra un servidor falso (Ollama, compatible OpenAI y el SDK de Anthropic, incluido el reintento y
la limpieza de campos inventados).

- **No probado:** ningún modelo real, ni cómo traduce tus frases; ni la lectura de `OrderItems`, ni de `bi_stock_vtex`, en tu base real.
- **Límites conocidos:** «cuántos clientes distintos» no se entiende como conteo de clientes; las preguntas con varias condiciones muy encadenadas pueden
  interpretarse a medias (la respuesta muestra los filtros que aplicó, en las etiquetas, para que lo notes).

## Columnas de OrderItems y de la maestra

El detalle del pedido, las preguntas por producto y las ventas por Clasif2 necesitan la **descripción** y el **precio** de cada línea. En tu base las líneas traen
`SKU_Name`, `SKU_Selling_Price` y `Reference_Code` (código SAP): el programa las reconoce solas y detecta si el precio viene en centavos (compara la suma de las
líneas con el total del pedido). Si otra base usa otros nombres, **no inventa nada**: lo dice con las columnas que sí existen y se indican en el `.env`
(`ITEM_COL_DESC`, `ITEM_COL_PRECIO`, `ITEM_PRECIO_CENTAVOS`). La primera consulta por producto después de arrancar descarga las líneas de todos los pedidos del
período (tarda algo más); luego solo se piden las de los pedidos que van llegando.

La **maestra de productos** (código SAP, Clasif2, producto) no se conoce: se indica la tabla en el `.env` (`MAESTRA_TABLA`, y `MAESTRA_ORIGEN=vtex` si no está
en el ODS). Mientras falte, el gráfico de ventas por Clasif2 lo explica y lista las tablas del servidor con nombres parecidos a una maestra.
