from logging.config import fileConfig
from pathlib import Path
import shutil
from datetime import datetime

from alembic import context
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.db import engine
from app.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def _copia_antes_de_migrar(conn) -> None:
    """Antes de cambiar la estructura de una base SQLite que ya tiene datos, deja una copia aparte (premigracion-*.db).
    No entra en la rotación de los respaldos diarios: no se pisa ni se borra sola."""
    if conn.dialect.name != "sqlite" or not engine.url.database or engine.url.database == ":memory:":
        return
    origen = Path(engine.url.database)
    if not origen.exists() or origen.stat().st_size == 0:
        return
    actual = MigrationContext.configure(conn).get_current_revision()
    pendiente = ScriptDirectory.from_config(context.config).get_current_head()
    if actual is None or actual == pendiente:
        return                                         # base nueva, o ya al día
    destino = origen.parent / "respaldos" if origen.parent.name == "data" else origen.parent
    destino.mkdir(parents=True, exist_ok=True)
    conn.exec_driver_sql("PRAGMA wal_checkpoint(FULL)")
    shutil.copy2(origen, destino / f"premigracion-{actual}-{datetime.now():%Y%m%d-%H%M%S}.db")


def run_migrations_online():
    with engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            # Recrear una tabla (batch) con las llaves foráneas activas borra en cascada las filas hijas: se apagan solo aquí.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            _copia_antes_de_migrar(conn)
            conn.commit()                                # cierra lo que abrieron estas consultas: alembic arranca su propia transacción
        context.configure(connection=conn, target_metadata=Base.metadata,
                          render_as_batch=conn.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
