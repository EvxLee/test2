from typing import Sequence, Union

from alembic import op


revision: str = "b9c8d7e6f5a4"
down_revision: Union[str, Sequence[str], None] = "a8f2c1d9e4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE master_dashboard.board_config
        SET monday_board_id = NULL,
            env_var_name = 'MONDAY_BOARD_PJT_IT',
            mapper_type = 'pjt_it',
            updated_at = now()
        WHERE board_key = 'pjt_it';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE master_dashboard.board_config
        SET monday_board_id = '1000000001',
            env_var_name = 'MONDAY_BOARD_PJT_IT',
            mapper_type = 'pjt_it',
            updated_at = now()
        WHERE board_key = 'pjt_it';
        """
    )
