"""add structured insurance policies

Revision ID: 20260903_0005
Revises: 20260731_0004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260903_0005"
down_revision: Union[str, None] = "20260731_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "insurance_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_type", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("required_documents", sa.JSON(), nullable=False),
        sa.Column("validation_rules", sa.JSON(), nullable=False),
        sa.Column("auto_approval_threshold", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("minimum_ocr_confidence", sa.Float(), nullable=False, server_default="0.70"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_insurance_policies_claim_type", "insurance_policies", ["claim_type"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_insurance_policies_claim_type", table_name="insurance_policies")
    op.drop_table("insurance_policies")
    op.drop_column("claims", "policy_version")
