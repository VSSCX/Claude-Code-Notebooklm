"""cuentas, sesiones, actividad y errores

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario', sa.Unicode(length=40), nullable=False),
        sa.Column('nombre', sa.Unicode(length=60), nullable=False),
        sa.Column('rol', sa.Unicode(length=12), nullable=False),
        sa.Column('clave_hash', sa.Unicode(length=200), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('debe_cambiar_clave', sa.Boolean(), nullable=False),
        sa.Column('creado', sa.DateTime(), nullable=False),
        sa.Column('ultimo_acceso', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_usuarios_usuario'), 'usuarios', ['usuario'], unique=True)
    op.create_table('sesiones',
        sa.Column('token_hash', sa.Unicode(length=64), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('creada', sa.DateTime(), nullable=False),
        sa.Column('vista', sa.DateTime(), nullable=False),
        sa.Column('ip', sa.Unicode(length=60), nullable=False),
        sa.Column('agente', sa.Unicode(length=200), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token_hash'))
    op.create_index(op.f('ix_sesiones_usuario_id'), 'sesiones', ['usuario_id'])
    op.create_index(op.f('ix_sesiones_vista'), 'sesiones', ['vista'])
    op.create_table('actividad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.Column('usuario', sa.Unicode(length=40), nullable=False),
        sa.Column('categoria', sa.Unicode(length=12), nullable=False),
        sa.Column('accion', sa.Unicode(length=200), nullable=False),
        sa.Column('entidad', sa.Unicode(length=40), nullable=False),
        sa.Column('resultado', sa.Unicode(length=10), nullable=False),
        sa.Column('detalle', sa.Unicode(length=400), nullable=False),
        sa.Column('ip', sa.Unicode(length=60), nullable=False),
        sa.Column('ms', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Unicode(length=16), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    for col in ('at', 'usuario', 'categoria', 'entidad', 'request_id'):
        op.create_index(op.f(f'ix_actividad_{col}'), 'actividad', [col])
    op.create_table('errores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('huella', sa.Unicode(length=40), nullable=False),
        sa.Column('nivel', sa.Unicode(length=10), nullable=False),
        sa.Column('origen', sa.Unicode(length=12), nullable=False),
        sa.Column('mensaje', sa.Unicode(length=400), nullable=False),
        sa.Column('traza', sa.UnicodeText(), nullable=False),
        sa.Column('ruta', sa.Unicode(length=200), nullable=False),
        sa.Column('primera', sa.DateTime(), nullable=False),
        sa.Column('ultima', sa.DateTime(), nullable=False),
        sa.Column('cuenta', sa.Integer(), nullable=False),
        sa.Column('estado', sa.Unicode(length=10), nullable=False),
        sa.Column('nota', sa.Unicode(length=400), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_errores_huella'), 'errores', ['huella'], unique=True)
    for col in ('origen', 'ultima', 'estado'):
        op.create_index(op.f(f'ix_errores_{col}'), 'errores', [col])
    op.create_table('errores_ocurrencias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('error_id', sa.Integer(), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.Column('usuario', sa.Unicode(length=40), nullable=False),
        sa.Column('request_id', sa.Unicode(length=16), nullable=False),
        sa.Column('metodo', sa.Unicode(length=8), nullable=False),
        sa.Column('ruta', sa.Unicode(length=200), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False),
        sa.Column('contexto', sa.UnicodeText(), nullable=False),
        sa.ForeignKeyConstraint(['error_id'], ['errores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'))
    for col in ('error_id', 'at', 'request_id'):
        op.create_index(op.f(f'ix_errores_ocurrencias_{col}'), 'errores_ocurrencias', [col])


def downgrade() -> None:
    op.drop_table('errores_ocurrencias')
    op.drop_table('errores')
    op.drop_table('actividad')
    op.drop_table('sesiones')
    op.drop_table('usuarios')
