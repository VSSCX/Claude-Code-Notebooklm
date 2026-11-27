"""cierre manual de pedidos

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-23

Agrega tres columnas opcionales a pedidos (cuándo se cerró, por qué y quién). Los pedidos que ya existen
quedan abiertos (cerrado = NULL): no se toca ningún dato.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pedidos") as b:
        b.add_column(sa.Column("cerrado", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("motivo_cierre", sa.Unicode(length=120), nullable=False, server_default=""))
        b.add_column(sa.Column("cerrado_por", sa.Unicode(length=60), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("pedidos") as b:
        b.drop_column("cerrado_por")
        b.drop_column("motivo_cierre")
        b.drop_column("cerrado")
