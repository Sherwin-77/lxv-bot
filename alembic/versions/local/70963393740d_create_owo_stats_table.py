"""create owo stats table

Revision ID: 70963393740d
Revises:
Create Date: 2025-06-02 21:18:18.858643

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70963393740d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'owo_stats',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('day', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('owo_count', sa.Integer(), nullable=False),
        sa.Column('hunt_count', sa.Integer(), nullable=False),
        sa.Column('battle_count', sa.Integer(), nullable=False),
        sa.Column('pray_count', sa.Integer(), nullable=False),
        sa.Column('curse_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('day', 'user_id'),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('owo_stats')
    # ### end Alembic commands ###
