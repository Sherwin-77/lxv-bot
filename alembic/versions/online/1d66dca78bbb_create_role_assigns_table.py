"""create role assigns table

Revision ID: 1d66dca78bbb
Revises: a8df008b8cb3
Create Date: 2025-03-01 20:04:21.061918

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d66dca78bbb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'role_assigns',
        sa.Column('id', sa.INTEGER, primary_key=True),
        sa.Column('role_id', sa.BIGINT, nullable=False, index=True),
        sa.Column('level', sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('role_assigns')
