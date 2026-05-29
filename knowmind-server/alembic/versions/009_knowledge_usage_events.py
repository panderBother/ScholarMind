"""knowledge usage events for analytics heatmap."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_knowledge_usage_events"
down_revision: Union[str, None] = "008_document_parse_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_usage_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_usage_events_kb_created",
        "knowledge_usage_events",
        ["kb_id", "created_at"],
    )
    op.create_index(
        "ix_usage_events_kb_type_created",
        "knowledge_usage_events",
        ["kb_id", "event_type", "created_at"],
    )
    op.create_index(
        "ix_usage_events_kb_item",
        "knowledge_usage_events",
        ["kb_id", "item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_kb_item", table_name="knowledge_usage_events")
    op.drop_index("ix_usage_events_kb_type_created", table_name="knowledge_usage_events")
    op.drop_index("ix_usage_events_kb_created", table_name="knowledge_usage_events")
    op.drop_table("knowledge_usage_events")
