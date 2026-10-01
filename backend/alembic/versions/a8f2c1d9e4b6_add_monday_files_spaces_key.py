from typing import Sequence, Union
from alembic import op


revision: str = "a8f2c1d9e4b6"
down_revision: Union[str, Sequence[str], None] = "c7f4a8b91e23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE monday.files
        ADD COLUMN IF NOT EXISTS spaces_key TEXT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE monday.files
        DROP COLUMN IF EXISTS spaces_key
    """)
