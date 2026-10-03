from logging.config import fileConfig

from alembic import context

from app.db import engine
from app.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def run_migrations_online():
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=Base.metadata,
                          render_as_batch=conn.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
