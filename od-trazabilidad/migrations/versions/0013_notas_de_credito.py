"""notas de crédito de entregas facturadas

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24

Solo crea una tabla nueva: no toca ninguna existente (no hay riesgo para los datos).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notas_credito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entrega_id", sa.Integer(), sa.ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.Unicode(length=40), nullable=False),
        sa.Column("sku", sa.Unicode(length=40), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motivo", sa.Unicode(length=120), nullable=False, server_default=""),
        sa.Column("usuario", sa.Unicode(length=60), nullable=False, server_default=""),
        sa.Column("at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notas_credito_entrega_id", "notas_credito", ["entrega_id"])
    op.create_index("ix_notas_credito_numero", "notas_credito", ["numero"])
    op.create_index("ix_notas_credito_at", "notas_credito", ["at"])


def downgrade() -> None:
    op.drop_table("notas_credito")
