"""create mods table

Revision ID: acb3665dd920
Revises: 1d66dca78bbb
Create Date: 2025-03-02 23:18:15.408227

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acb3665dd920'
down_revision: Union[str, None] = '1d66dca78bbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mods',
        sa.Column('id', sa.BIGINT, primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('mods')
