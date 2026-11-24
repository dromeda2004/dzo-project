"""Address archiving (epic4.task2).

Addresses an order has used are archived rather than deleted or edited in place.

Revision ID: 7880f8584eb7
Revises: 75bea9e4303e
Create Date: 2026-11-23 20:16:23.214223

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7880f8584eb7"
down_revision: str | None = "75bea9e4303e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "addresses",
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    # Archived addresses become visible again; they are still valid addresses.
    op.drop_column("addresses", "is_archived")
