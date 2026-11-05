"""restricción por cliente: un producto por pallet (SDA Stock)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clientes") as b:
        b.add_column(sa.Column("pallet_por_producto", sa.Boolean(), nullable=False, server_default=sa.false()))
    # FALABELLA y EASY: cada producto en su pallet, sin mezclar (los demás clientes no cambian)
    op.execute("UPDATE clientes SET pallet_por_producto = 1 WHERE nombre IN ('FALABELLA', 'EASY')")


def downgrade() -> None:
    with op.batch_alter_table("clientes") as b:
        b.drop_column("pallet_por_producto")
