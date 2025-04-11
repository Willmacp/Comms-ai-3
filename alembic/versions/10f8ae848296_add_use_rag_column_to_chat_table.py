"""Add use_rag column to chat table

Revision ID: 10f8ae848296
Revises: 8a2f8810f8f8
Create Date: 2024-10-17 15:30:16.798365

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "10f8ae848296"
down_revision: Union[str, None] = "8a2f8810f8f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    op.add_column("chat", sa.Column("use_rag", sa.Boolean(), server_default="true", nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    op.drop_column("chat", "use_rag")

    # ### end Alembic commands ###
