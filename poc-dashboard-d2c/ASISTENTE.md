# Asistente de consultas (el chat del icono de arriba)

Pregunta en español cosas como:

- «¿Cuántas unidades del refrigerador MED 165B cayeron hoy?»
- «¿Cuántos pedidos de MELI ayer?» y luego «¿y de Falabella?»
- «Top 5 productos más vendidos este mes»
- «Monto de pedidos no integrados esta semana»
- «Unidades de la lavadora 8,5 kg los últimos 7 días por día»
- «Pedido 3506611» (te deja abrir su detalle)

Entiende: unidades, pedidos, líneas y montos; producto (por nombre o por código SAP de 9 dígitos); períodos (hoy, ayer, esta semana,
semana pasada, este mes, mes pasado, últimos N días, un mes por nombre, una fecha o un rango); cliente (MELI, Falabella...), canal
(BWS, MKP), bodega (EC01, POST_Fechado...), estado (no integrado, integrado, pendiente, facturado, cancelado) y desgloses «por día,
cliente, canal, bodega, estado, producto». Si no dices el período usa el mes en curso. Por defecto no cuenta los pedidos cancelados
y lo dice en la respuesta (si preguntas por cancelados, los cuenta).

## Cómo funciona (y por qué es seguro)

```
pregunta ──► 1. PLAN (JSON con campos fijos) ──► 2. VALIDACIÓN (listas permitidas) ──► 3. CÁLCULO (pandas, en el servidor)
             reglas en español, o una IA                                                  cifra + tabla + chips
```

1. **Plan.** Por defecto lo arma un conjunto de reglas en español (sin IA, sin internet, sin costo, siempre disponible). Si configuras una
   IA, la IA hace solo este paso: devuelve un JSON con `metrica`, `producto`, `periodo`, `cliente`... Si falla, no responde o devuelve
   algo inválido, el asistente usa las reglas.
2. **Validación.** Cada campo se compara con listas permitidas (métricas, períodos, y los canales, clientes y bodegas que existen de verdad).
   Lo que no calza se descarta.
3. **Cálculo.** El servidor calcula la cifra con pandas sobre los datos que ya tiene en memoria (y las líneas de OrderItems para productos).
   Nunca se ejecuta SQL ni código escrito por una IA.

Por eso, aunque la IA se equivoque o alguien intente engañarla con el texto de la pregunta, lo peor que pasa es que la pregunta se
interprete mal: no puede leer otras tablas, ni cambiar datos, ni ejecutar nada.

**Privacidad.** Con IA, al modelo solo se le envía el texto de la pregunta, la fecha de hoy y los nombres de canales, clientes y bodegas.
Nunca pedidos, montos ni productos. Aun así, con un modelo externo ese texto sale de tu red: prefiere un modelo local, y la cabecera
del chat indica «IA local» o «IA externa». El chat tiene un tope de 40 preguntas por minuto en el servidor.

## Activar una IA (opcional)

Edita el `.env` del equipo servidor y reinicia `servidor.bat`:

| Quiero usar | `.env` |
|---|---|
| Ollama en el mismo equipo (local) | `IA_MODO=ollama`  `IA_URL=http://localhost:11434`  `IA_MODELO=qwen2.5:7b` |
| LM Studio, vLLM, llama.cpp u otro servidor «compatible con OpenAI» | `IA_MODO=openai`  `IA_URL=http://localhost:1234/v1`  `IA_MODELO=<nombre del modelo>` |
| Claude (Anthropic) | `IA_MODO=anthropic`  `IA_CLAVE=<tu clave>`  `IA_MODELO=claude-haiku-4-5-20251001` |

Para Ollama: `ollama pull qwen2.5:7b` y listo (usa el modo JSON de Ollama para forzar la salida estructurada). Un modelo de 7 a 8 mil
millones de parámetros alcanza para esta tarea, porque solo traduce frases cortas a un JSON pequeño y entiende español; no hace falta GPU
grande. Alternativas razonables: `llama3.1:8b`, `qwen2.5:14b`, `mistral-nemo`. No medí cuál traduce mejor tus preguntas reales: pruébalos con
las 10 preguntas que más haces.

Cada pregunta con IA suma unos segundos (según el modelo y el equipo). Si la IA tarda más de `IA_TIMEOUT_SEGUNDOS` (25 por defecto) o falla, el
asistente responde igual con las reglas y lo avisa en una nota.

## Qué repositorios y agentes se revisaron

La idea inicial era usar un agente «texto a SQL / pandas» ya hecho. Se revisaron estos y se decidió **no** incrustarlos (sí aprovechar su idea
de «la IA traduce, otro componente ejecuta»):

| Proyecto | Qué hace | Por qué no se usó directamente |
|---|---|---|
| [Vanna](https://vanna.ai/) (MIT) | Genera SQL con un LLM más RAG sobre tu esquema | La IA escribiría SQL contra la base de pedidos. Para este tablero, publicado a toda la red, prefiero que la IA no ejecute nada |
| [PandasAI](https://docs.pandas-ai.com/) | Convierte preguntas en código Python/SQL y lo ejecuta (con sandbox Docker) | Ejecuta código generado por el modelo: exige Docker o aislamiento y más dependencias en un PC de empresa |
| [LangChain SQL / pandas agents](https://python.langchain.com/) | Agente que explora la base y escribe consultas | Dependencia grande, comportamiento menos predecible y ejecución de consultas generadas |
| [DB-GPT-Hub](https://github.com/eosphoros-ai/db-gpt-hub) y listas como [Awesome-Text2SQL](https://github.com/eosphoros-ai/Awesome-Text2SQL) | Modelos afinados y benchmarks de texto a SQL (por ejemplo variantes de Llama y Qwen) | Útiles si algún día se quiere SQL libre; hoy las preguntas son un conjunto acotado y se resuelven mejor con un plan validado |
| [Ollama](https://ollama.com/) | Servidor local de modelos con salida JSON estructurada | **Sí soportado** como motor opcional (`IA_MODO=ollama`) |

Si más adelante quieres preguntas más libres (por ejemplo comparar períodos o preguntar por la fecha de entrega), se extiende el plan con
nuevos campos y se valida igual; no hace falta que la IA escriba SQL.

## Qué está probado y qué no

- Probado aquí con los datos de ejemplo: el motor de reglas con las preguntas de arriba, las preguntas de seguimiento («¿y ayer?»), productos
  que no existen (sugiere los más parecidos), preguntas que no entiende, y los tres modos de IA contra un servidor falso que imita las
  respuestas de Ollama, de un servidor compatible con OpenAI y de Anthropic (se verifica la forma de la petición, el JSON devuelto, la
  limpieza de valores inventados y el respaldo a las reglas).
- **No probado:** ninguno de los modelos reales ni la calidad de su traducción de tus preguntas; ni la lectura de OrderItems en tu base real
  (ver abajo).

## Importante: columnas de OrderItems en tu base real

El detalle del pedido y las preguntas por producto necesitan la **descripción** y el **precio** de cada línea. En esta carpeta solo se
conocían `Sequence`, `Quantity_SKU`, `Reference_Code` (el código SAP), `SLA_Type`, `warehouse` y `Shipping_Estimate_Date`. El programa busca
columnas con nombres típicos (`SKU_Name`, `Name`, `Description`, `Selling_Price`, `Price`...) y detecta si el precio viene en centavos (compara
la suma de las líneas con el total del pedido). Si no las encuentra, **no inventa nada**: el cajón del pedido muestra un aviso con las
columnas que sí existen, y entonces se indican en el `.env` (`ITEM_COL_DESC`, `ITEM_COL_PRECIO`, `ITEM_PRECIO_CENTAVOS`). Mándame ese aviso y lo
dejo fijo.

La primera pregunta por producto después de arrancar descarga las líneas de todos los pedidos del período (tarda algo más); luego solo
se piden las líneas de los pedidos que van llegando.
