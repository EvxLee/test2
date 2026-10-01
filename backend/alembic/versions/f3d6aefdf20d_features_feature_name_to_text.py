"""features.feature_name to TEXT

Revision ID: f3d6aefdf20d
Revises: e1d740704e0d
Create Date: 2025-08-21 18:55:28.921073

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3d6aefdf20d'
down_revision: Union[str, Sequence[str], None] = 'e1d740704e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "features",
        "feature_name",
        type_=sa.Text(),
        existing_type=sa.VARCHAR(length=200),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "features",
        "feature_name",
        type_=sa.VARCHAR(length=200),
        existing_type=sa.Text(),
        existing_nullable=False,
    )
