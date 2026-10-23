"""categoría de grupo en las entregas y referencia de cita sin tope de 30 caracteres

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22

Ojo: en SQLite NO se usa batch_alter_table para ensanchar la columna. Cambiar el tipo de una columna obliga a SQLite a recrear la
tabla `entregas` y, con las llaves foráneas activas, borrar la tabla vieja arrastra (ON DELETE CASCADE) sus líneas, pasos e
historial. SQLite no hace cumplir el largo de un VARCHAR, así que ahí no hace falta tocar nada.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entregas", sa.Column("categoria", sa.Unicode(length=20), nullable=False, server_default=""))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("entregas", "cita_numero", existing_type=sa.Unicode(length=30), type_=sa.Unicode(length=120),
                        existing_nullable=False)


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("entregas", "cita_numero", existing_type=sa.Unicode(length=120), type_=sa.Unicode(length=30),
                        existing_nullable=False)
    with op.batch_alter_table("entregas") as b:
        b.drop_column("categoria")
