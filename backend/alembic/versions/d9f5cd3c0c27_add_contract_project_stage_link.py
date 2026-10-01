"""add_contract_project_stage_link

Revision ID: d9f5cd3c0c27
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16 18:11:44.082728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9f5cd3c0c27'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add project_id and project_stage_id to contract_status for linking contracts to projects/stages"""
    op.execute(
        """
        ALTER TABLE master_dashboard.contract_status
          ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES master_dashboard.projects(id),
          ADD COLUMN IF NOT EXISTS project_stage_id UUID REFERENCES master_dashboard.project_stages(id)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contract_status_project_id "
        "ON master_dashboard.contract_status (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contract_status_project_stage_id "
        "ON master_dashboard.contract_status (project_stage_id)"
    )


def downgrade() -> None:
    """Remove project link columns from contract_status (indexes are dropped with the columns)."""
    op.execute(
        "ALTER TABLE master_dashboard.contract_status "
        "DROP COLUMN IF EXISTS project_id, DROP COLUMN IF EXISTS project_stage_id"
    )
