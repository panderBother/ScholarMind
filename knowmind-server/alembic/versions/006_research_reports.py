"""research reports from conversations

Revision ID: 006_research_reports
Revises: 005_distill_logs
Create Date: 2026-05-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_research_reports"
down_revision: Union[str, None] = "005_distill_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("raw_answer_md", sa.Text(), nullable=True),
        sa.Column("outline_json", sa.JSON(), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="ready", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_reports_user_updated", "research_reports", ["user_id", "updated_at"])
    op.create_index("ix_reports_kb_updated", "research_reports", ["kb_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_kb_updated", table_name="research_reports")
    op.drop_index("ix_reports_user_updated", table_name="research_reports")
    op.drop_table("research_reports")
