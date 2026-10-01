from typing import Sequence, Union
from alembic import op


revision: str = 'c7f4a8b91e23'
down_revision: Union[str, Sequence[str], None] = '9d08f2ea3af2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS llm.embedding_runs (
            source_type      TEXT PRIMARY KEY,
            last_run_at      TIMESTAMPTZ,
            chunks_processed INT
        )
    """)
    op.execute("""
        ALTER TABLE llm.documents
        ADD COLUMN IF NOT EXISTS file_type TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE llm.documents DROP COLUMN IF EXISTS file_type")
    op.execute("DROP TABLE IF EXISTS llm.embedding_runs")
