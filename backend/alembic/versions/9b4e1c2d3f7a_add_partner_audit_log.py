"""add partner_audit_log table

Revision ID: 9b4e1c2d3f7a
Revises: f3d6aefdf20d
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b4e1c2d3f7a'
down_revision: Union[str, Sequence[str], None] = 'f3d6aefdf20d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'partner_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('duplicate_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('partner_audit_log')
