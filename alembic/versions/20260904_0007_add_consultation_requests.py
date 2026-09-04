"""add consultation requests

Revision ID: 20260904_0007
Revises: 20260903_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260904_0007"
down_revision = "20260903_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultation_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(60)),
        sa.Column("product_interest", sa.String(180)),
        sa.Column("preferred_time", sa.String(180)),
        sa.Column("question", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_consultation_requests_user_id", "consultation_requests", ["user_id"])
    op.create_index("ix_consultation_requests_status", "consultation_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_consultation_requests_status", table_name="consultation_requests")
    op.drop_index("ix_consultation_requests_user_id", table_name="consultation_requests")
    op.drop_table("consultation_requests")
