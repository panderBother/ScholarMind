"""working memory facts and incremental document chunks

Revision ID: 013_planner_memory_incremental
Revises: 012_mediumtext_content
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_planner_memory_incremental"
down_revision: Union[str, None] = "012_mediumtext_content"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.String(36, collation="utf8mb4_0900_ai_ci")
    op.create_table(
        "conversation_facts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("conversation_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("fact_key", sa.String(128), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("source_message_id", uuid_type, nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("conversation_id", "fact_key", name="uq_conv_fact_key"),
    )
    op.create_index(
        "ix_conversation_facts_conversation_id", "conversation_facts", ["conversation_id"]
    )
    op.create_index("ix_conversation_facts_user_id", "conversation_facts", ["user_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, nullable=False),
        sa.Column("chunk_id", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chunk_id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_content_hash", "document_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("conversation_facts")
