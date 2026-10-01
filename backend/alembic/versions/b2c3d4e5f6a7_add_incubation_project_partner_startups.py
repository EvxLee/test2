"""add incubation_project_partner_startups table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS master_dashboard.incubation_project_partner_startups (
            id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            monday_item_id          BIGINT      NOT NULL,
            source_board            TEXT        NOT NULL,
            project_name            TEXT,
            stage                   TEXT        NOT NULL,
            stage_column_id         TEXT,
            stage_column_title      TEXT,
            startup_monday_item_id  BIGINT      NULL,
            startup_name            TEXT        NOT NULL,
            source_display_value    TEXT,
            ingested_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_proj_stage_startup
                UNIQUE (monday_item_id, stage, startup_name)
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ipps_monday_item_id "
        "ON master_dashboard.incubation_project_partner_startups (monday_item_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ipps_source_board "
        "ON master_dashboard.incubation_project_partner_startups (source_board);"
    )


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS master_dashboard.incubation_project_partner_startups;"
    )
