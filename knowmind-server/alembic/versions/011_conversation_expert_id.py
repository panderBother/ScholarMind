"""conversations.expert_id for expert agent sessions

Revision ID: 011_conversation_expert_id
Revises: 010_expert_agents
Create Date: 2026-05-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_conversation_expert_id"
down_revision: Union[str, None] = "010_expert_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("expert_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_expert_id",
        "conversations",
        "expert_agents",
        ["expert_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_expert_id", "conversations", ["expert_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_expert_id", table_name="conversations")
    op.drop_constraint("fk_conversations_expert_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "expert_id")
