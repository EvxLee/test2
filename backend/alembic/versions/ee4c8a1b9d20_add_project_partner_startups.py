"""add project_partner_startups table

Revision ID: ee4c8a1b9d20
Revises: b2c3d4e5f6a7, d9f5cd3c0c27
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "ee4c8a1b9d20"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "d9f5cd3c0c27")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS master_dashboard.project_partner_startups (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id   UUID        NOT NULL
                         REFERENCES master_dashboard.projects(id)
                         ON DELETE CASCADE,
            stage        TEXT        NOT NULL,
            startup_name TEXT        NOT NULL,
            ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_project_partner_startup
                UNIQUE (project_id, stage, startup_name)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_project_partner_startups_project_id "
        "ON master_dashboard.project_partner_startups (project_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_project_partner_startups_stage "
        "ON master_dashboard.project_partner_startups (stage);"
    )


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS master_dashboard.project_partner_startups;"
    )
