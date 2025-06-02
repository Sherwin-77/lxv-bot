"""create custom roles table

Revision ID: 376e79b5d23c
Revises: acb3665dd920
Create Date: 2025-03-03 23:28:27.450492

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '376e79b5d23c'
down_revision: Union[str, None] = 'acb3665dd920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'custom_roles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('role_id', sa.BIGINT, nullable=False),
        sa.Column('user_id', sa.BIGINT, nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table('custom_roles')
