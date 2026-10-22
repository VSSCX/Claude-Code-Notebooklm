"""categoría de grupo en las entregas y referencia de cita sin tope de 30 caracteres

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.add_column(sa.Column("categoria", sa.Unicode(length=20), nullable=False, server_default=""))
        b.alter_column("cita_numero", existing_type=sa.Unicode(length=30), type_=sa.Unicode(length=120),
                       existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.alter_column("cita_numero", existing_type=sa.Unicode(length=120), type_=sa.Unicode(length=30),
                       existing_nullable=False)
        b.drop_column("categoria")
