"""suministros: tandas de un mismo pedido

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.add_column(sa.Column("suministro", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.drop_column("suministro")
