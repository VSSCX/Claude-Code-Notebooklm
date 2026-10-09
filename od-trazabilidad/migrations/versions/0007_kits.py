"""kits (SKU que reúne cajas separadas)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kits",
        sa.Column("sku", sa.Unicode(length=40), primary_key=True),
        sa.Column("descripcion", sa.Unicode(length=200), nullable=False, server_default=""),
        sa.Column("actualizado", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kit_componentes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kit_sku", sa.Unicode(length=40), sa.ForeignKey("kits.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.Unicode(length=40), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("kit_sku", "sku", name="uq_kit_componente"),
    )
    op.create_index("ix_kit_componentes_kit_sku", "kit_componentes", ["kit_sku"])


def downgrade() -> None:
    op.drop_index("ix_kit_componentes_kit_sku", table_name="kit_componentes")
    op.drop_table("kit_componentes")
    op.drop_table("kits")
