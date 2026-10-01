"""add venture column to gced_mftf25_startups

Revision ID: a1b2c3d4e5f6
Revises: 9b4e1c2d3f7a
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9b4e1c2d3f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE master_dashboard.gced_mftf25_startups "
        "ADD COLUMN IF NOT EXISTS venture TEXT;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE master_dashboard.gced_mftf25_startups "
        "DROP COLUMN IF EXISTS venture;"
    )
