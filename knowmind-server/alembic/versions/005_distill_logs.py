"""rag logs, feedback, knowledge gaps

Revision ID: 005_distill_logs
Revises: 004_knowledge_items
Create Date: 2026-05-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_distill_logs"
down_revision: Union[str, None] = "004_knowledge_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_retrieval_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("hit_scores", sa.JSON(), nullable=True),
        sa.Column("top_item_ids", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
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
    op.create_index("ix_rag_logs_kb_created", "rag_retrieval_logs", ["kb_id", "created_at"])

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("message_id", sa.String(length=36), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=False),
        sa.Column("topic_key", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_user_feedback_kb_topic", "user_feedback", ["kb_id", "topic_key"])

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("gap_key", sa.String(length=256), nullable=False),
        sa.Column("trigger_rule", sa.String(length=64), nullable=False),
        sa.Column("sample_queries", sa.JSON(), nullable=False),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("draft_item_ids", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_knowledge_gaps_kb_status", "knowledge_gaps", ["kb_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_gaps_kb_status", table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
    op.drop_index("ix_user_feedback_kb_topic", table_name="user_feedback")
    op.drop_table("user_feedback")
    op.drop_index("ix_rag_logs_kb_created", table_name="rag_retrieval_logs")
    op.drop_table("rag_retrieval_logs")
