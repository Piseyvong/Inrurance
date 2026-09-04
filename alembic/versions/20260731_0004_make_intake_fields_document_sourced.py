"""make intake fields document sourced

Revision ID: 20260731_0004
Revises: 20260731_0003
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0004"
down_revision: Union[str, None] = "20260731_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("claims") as batch_op:
        batch_op.alter_column("claimant_name", existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column("policy_number", existing_type=sa.String(length=100), nullable=True)
        batch_op.alter_column("incident_date", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column("claims", "incident_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("claims", "policy_number", existing_type=sa.String(length=100), nullable=False)
    op.alter_column("claims", "claimant_name", existing_type=sa.String(length=255), nullable=False)
