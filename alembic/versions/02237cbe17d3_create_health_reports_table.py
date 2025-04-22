"""add reports table

Revision ID: 02237cbe17d3
Revises: 376e79b5d23c
Create Date: 2025-04-22 11:07:55.681684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '02237cbe17d3'
down_revision: Union[str, None] = '376e79b5d23c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("health_reports")
