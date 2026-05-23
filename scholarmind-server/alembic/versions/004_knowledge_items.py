"""knowledge_categories and knowledge_items

Revision ID: 004_knowledge_items
Revises: 003_conversations_chat
Create Date: 2026-05-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_knowledge_items"
down_revision: Union[str, None] = "003_conversations_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.ForeignKeyConstraint(["parent_id"], ["knowledge_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_knowledge_categories_kb_id", "knowledge_categories", ["kb_id"], unique=False)

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kb_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("access_level", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=True),
        sa.Column("chunk_id", sa.String(length=36), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["knowledge_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_knowledge_items_kb_id", "knowledge_items", ["kb_id"], unique=False)
    op.create_index("ix_knowledge_items_user_id", "knowledge_items", ["user_id"], unique=False)
    op.create_index("ix_knowledge_items_document_id", "knowledge_items", ["document_id"], unique=False)
    op.create_index("ix_knowledge_items_category_id", "knowledge_items", ["category_id"], unique=False)
    op.create_index("ix_knowledge_items_chunk_id", "knowledge_items", ["chunk_id"], unique=False)
    op.create_index(
        "ix_knowledge_items_lifecycle_status",
        "knowledge_items",
        ["lifecycle_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_items_lifecycle_status", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_chunk_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_category_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_document_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_user_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_kb_id", table_name="knowledge_items")
    op.drop_table("knowledge_items")
    op.drop_index("ix_knowledge_categories_kb_id", table_name="knowledge_categories")
    op.drop_table("knowledge_categories")
