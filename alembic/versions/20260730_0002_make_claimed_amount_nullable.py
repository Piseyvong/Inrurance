"""make claimed amount nullable

Revision ID: 20260730_0002
Revises: 20260729_0001
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0002"
down_revision: Union[str, None] = "20260729_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("claims") as batch_op:
        batch_op.alter_column("claimed_amount", existing_type=sa.Numeric(12, 2), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "claims",
        "claimed_amount",
        existing_type=sa.Numeric(12, 2),
        nullable=False,
    )
