"""camión compartido entre pedidos

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.add_column(sa.Column("camion_ref", sa.Unicode(length=40), nullable=False, server_default=""))
        b.create_index("ix_entregas_camion_ref", ["camion_ref"])


def downgrade() -> None:
    with op.batch_alter_table("entregas") as b:
        b.drop_index("ix_entregas_camion_ref")
        b.drop_column("camion_ref")
