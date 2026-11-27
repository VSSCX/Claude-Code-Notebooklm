"""notas cortas por grupo

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-26

Solo crea una tabla nueva: no toca ninguna existente (no hay riesgo para los datos).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.Unicode(length=60), nullable=False),
        sa.Column("texto", sa.Unicode(length=300), nullable=False),
        sa.Column("usuario", sa.Unicode(length=60), nullable=False, server_default=""),
        sa.Column("at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notas_clave", "notas", ["clave"])
    op.create_index("ix_notas_at", "notas", ["at"])


def downgrade() -> None:
    op.drop_index("ix_notas_at", table_name="notas")
    op.drop_index("ix_notas_clave", table_name="notas")
    op.drop_table("notas")
