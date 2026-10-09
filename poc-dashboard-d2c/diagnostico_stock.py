"""Por que tarda la consulta de stock VTEX: mide cada parte por separado, muestra los tipos de las columnas y los indices.
Uso (en el equipo que se conecta a las bases):   python diagnostico_stock.py          (opcional: --origen vtex)
No modifica nada: solo lee."""
import argparse
import sys
import time

from app import queries
from app.db import leer_sap, leer_vtex

ap = argparse.ArgumentParser()
ap.add_argument("--origen", default="sap", choices=["sap", "vtex"])
ap.add_argument("--timeout", type=int, default=180)
a = ap.parse_args()
leer = leer_vtex if a.origen == "vtex" else leer_sap


def medir(titulo, sql):
    t0 = time.time()
    try:
        df = leer(sql, timeout=a.timeout)
        print(f"  {time.time() - t0:6.1f} s  {titulo}" + (f"  ->  {df.iloc[0, 0]}" if df.shape == (1, 1) else f"  ->  {len(df)} filas"), flush=True)
        return df
    except Exception as e:  # noqa: BLE001
        print(f"  {time.time() - t0:6.1f} s  {titulo}  ->  ERROR: {str(e)[:150]}", flush=True)
        return None


print("1. Cada parte de la consulta por separado")
medir("MAX(fechaActualizacion) de la maestra", "SET NOCOUNT ON; SELECT MAX(fechaActualizacion) FROM bi_vtex_maestra_producto")
medir("MAX(fecha) de bi_vtex_stock", "SET NOCOUNT ON; SELECT MAX(fecha) FROM bi_vtex_stock")
medir("filas de la ultima fecha", "SET NOCOUNT ON; SELECT COUNT(*) FROM bi_vtex_stock WHERE fecha=(SELECT MAX(fecha) FROM bi_vtex_stock)")
medir("filas totales de bi_vtex_stock", "SET NOCOUNT ON; SELECT COUNT(*) FROM bi_vtex_stock")
medir("filas totales de la maestra", "SET NOCOUNT ON; SELECT COUNT(*) FROM bi_vtex_maestra_producto")
print("\n2. La consulta completa (la que usa el tablero)")
t0 = time.time()
df = medir("consulta de stock completa", queries.SQL_STOCK)

print("\n3. Tipos de las columnas que se comparan (si no son texto, SQL Server convierte fila por fila y no usa indices)")
tipos = medir("tipos", """SET NOCOUNT ON; SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH AS largo
  FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME IN ('bi_vtex_stock','bi_vtex_maestra_producto')
  AND COLUMN_NAME IN ('fecha','horario','warehouseId','skuId','id','totalQuantity','reservedQuantity','fechaActualizacion','codigoSap')
  ORDER BY TABLE_NAME, COLUMN_NAME""")
if tipos is not None:
    print(tipos.to_string(index=False))
print("\n4. Indices existentes (sin un indice por fecha/horario, cada consulta recorre toda la tabla)")
idx = medir("indices", """SET NOCOUNT ON; SELECT t.name AS tabla, i.name AS indice, i.type_desc AS tipo,
  STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columnas
  FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id
  JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=0
  JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
  WHERE t.name IN ('bi_vtex_stock','bi_vtex_maestra_producto') GROUP BY t.name, i.name, i.type_desc""")
if idx is not None:
    print(idx.to_string(index=False))
print("""
Como leerlo:
  - Si las partes de la seccion 1 son rapidas pero la completa es lenta, el problema es el JOIN o los filtros (NOT LIKE '10000%' sobre un numero convierte cada fila).
  - Si MAX(fecha) ya es lento, falta un indice por fecha en bi_vtex_stock.
  - Si 'fecha', 'horario' o 'fechaActualizacion' no son texto (nvarchar), compararlas con las variables de texto de la consulta obliga a convertir toda la columna.
  - Si falta un indice en bi_vtex_stock(fecha, horario, warehouseId) o en la maestra(id, fechaActualizacion), pidele a quien administra el ODS que lo cree
    o que deje una vista/tabla con el stock actual (por ejemplo bi_stock_vtex_actual) y se lee eso con STOCK_TABLA.""")
sys.exit(0)
