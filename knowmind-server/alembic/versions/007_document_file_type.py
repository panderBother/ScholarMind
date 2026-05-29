"""Revision: document file_type + preview fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_document_file_type"
down_revision: Union[str, None] = "006_research_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_type", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("parsed_title", sa.String(512), nullable=True))
    op.add_column("documents", sa.Column("parsed_summary", sa.String(500), nullable=True))
    op.add_column("documents", sa.Column("parsed_content", sa.Text(), nullable=True))
    op.execute("UPDATE documents SET file_type = 'pdf' WHERE file_type IS NULL")


def downgrade() -> None:
    op.drop_column("documents", "parsed_content")
    op.drop_column("documents", "parsed_summary")
    op.drop_column("documents", "parsed_title")
    op.drop_column("documents", "file_type")
