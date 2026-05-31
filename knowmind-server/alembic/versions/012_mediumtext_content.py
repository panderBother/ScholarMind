"""documents.parsed_content / knowledge_items.content → MEDIUMTEXT

Revision ID: 012_mediumtext_content
Revises: 011_conversation_expert_id
Create Date: 2026-05-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "012_mediumtext_content"
down_revision: Union[str, None] = "011_conversation_expert_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    medium = mysql.MEDIUMTEXT()
    op.alter_column(
        "documents",
        "parsed_content",
        existing_type=sa.Text(),
        type_=medium,
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_items",
        "content",
        existing_type=sa.Text(),
        type_=medium,
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    plain = sa.Text()
    op.alter_column(
        "knowledge_items",
        "content",
        existing_type=mysql.MEDIUMTEXT(),
        type_=plain,
        existing_nullable=False,
    )
    op.alter_column(
        "documents",
        "parsed_content",
        existing_type=mysql.MEDIUMTEXT(),
        type_=plain,
        existing_nullable=True,
    )
