"""Revision: document parse progress fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_document_parse_progress"
down_revision: Union[str, None] = "007_document_file_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("parse_progress", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("documents", sa.Column("parse_stage", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "parse_stage")
    op.drop_column("documents", "parse_progress")
