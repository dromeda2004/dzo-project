"""Restaurant opening hours and the pause toggle (epic4.task3).

Revision ID: f0b187048918
Revises: 7880f8584eb7
Create Date: 2026-11-24 21:25:16.157388

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0b187048918"
down_revision: str | None = "7880f8584eb7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "restaurant_hours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_restaurant_hours_day_of_week"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_restaurant_hours_restaurant_id"),
        "restaurant_hours",
        ["restaurant_id"],
        unique=False,
    )
    op.add_column(
        "restaurants", sa.Column("orders_paused_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("restaurants", "orders_paused_at")
    op.drop_index(op.f("ix_restaurant_hours_restaurant_id"), table_name="restaurant_hours")
    op.drop_table("restaurant_hours")
