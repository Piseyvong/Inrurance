"""persist semantic extraction normalization and traceability

Revision ID: 20260910_0009
Revises: 20260910_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0009"
down_revision = "20260910_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("extracted_fields")}
    for column in (
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("semantic_reason", sa.Text(), nullable=True),
    ):
        if column.name not in existing:
            op.add_column("extracted_fields", column)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("extracted_fields")}
    for name in ("semantic_reason", "source_text", "normalized_value"):
        if name in existing:
            op.drop_column("extracted_fields", name)
