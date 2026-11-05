"""Prueba la conexión a SQL Server y muestra qué hay disponible.

    py herramientas\\probar_sql.py                 (usa BASES_URL del .env)
    py herramientas\\probar_sql.py plan            (busca tablas/vistas con "plan")
    py herramientas\\probar_sql.py plan --columnas (además muestra sus columnas)

Solo lee metadatos: no consulta datos ni escribe nada.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.integrations.bases import motor_bases  # noqa: E402


def main():
    if not settings.bases_url:
        raise SystemExit(
            "Falta BASES_URL en .env. Ejemplo (autenticación de Windows):\n"
            "BASES_URL=mssql+pyodbc://SERVIDOR/BASE?driver=ODBC+Driver+17+for+SQL+Server"
            "&trusted_connection=yes&TrustServerCertificate=yes")
    filtro = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    columnas = "--columnas" in sys.argv

    try:
        engine = motor_bases()
        print("Entrando como:", settings.bases_usuario or "tu cuenta de Windows")
        with engine.connect() as cx:
            print("Conectado:", cx.execute(text("SELECT @@VERSION")).scalar_one().split("\n")[0])
            filas = cx.execute(text("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE (:f = '' OR TABLE_NAME LIKE '%' + :f + '%')
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """), {"f": filtro}).all()
            print(f"\n{len(filas)} tablas/vistas" + (f" que contienen '{filtro}'" if filtro else ""))
            for esquema, nombre, tipo in filas[:60]:
                print(f"  {esquema}.{nombre}  ({'vista' if 'VIEW' in tipo else 'tabla'})")
                if columnas:
                    cols = cx.execute(text("""
                        SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = :e AND TABLE_NAME = :t ORDER BY ORDINAL_POSITION
                    """), {"e": esquema, "t": nombre}).all()
                    print("      " + ", ".join(f"{c} {t}" for c, t in cols))
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        pista = ""
        if "Data source name not found" in msg or "IM002" in msg:
            pista = "\nPista: falta el ODBC Driver for SQL Server, o el nombre del driver no coincide."
        elif "Login failed" in msg:
            pista = ("\nPista: el usuario o la clave no son válidos."
                     if settings.bases_usuario else
                     "\nPista: tu cuenta de Windows no tiene acceso. Usa BASES_USUARIO/BASES_CLAVE o pide acceso a TI.")
        elif "certificate" in msg.lower():
            pista = "\nPista: agrega &TrustServerCertificate=yes a la URL."
        raise SystemExit(f"ERROR de conexión: {msg[:400]}{pista}")


if __name__ == "__main__":
    main()
