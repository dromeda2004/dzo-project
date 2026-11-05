"""menu categories, modifier limits, item archiving, lowercase email index

Revision ID: e244c811d626
Revises: d8248da4da9e
Create Date: 2026-11-04 20:00:40.764353

See docs/EPIC3_TRACKER.md epic3.task3. The lowercase email index fails to build if
two existing accounts differ only in case; there are none outside local dev data.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e244c811d626"
down_revision: str | None = "d8248da4da9e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_menu_categories_restaurant_id"), "menu_categories", ["restaurant_id"], unique=False
    )

    op.add_column("menu_items", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column(
        "menu_items", sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "menu_items",
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(op.f("ix_menu_items_category_id"), "menu_items", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_menu_items_category_id",
        "menu_items",
        "menu_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # is_required becomes min_selections: required groups need at least one choice.
    op.add_column(
        "menu_item_modifiers",
        sa.Column("min_selections", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("menu_item_modifiers", sa.Column("max_selections", sa.Integer(), nullable=True))
    op.add_column(
        "menu_item_modifiers",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute("UPDATE menu_item_modifiers SET min_selections = 1 WHERE is_required")
    op.drop_column("menu_item_modifiers", "is_required")
    op.create_check_constraint(
        "ck_modifier_min_selections_nonnegative", "menu_item_modifiers", "min_selections >= 0"
    )
    op.create_check_constraint(
        "ck_modifier_max_selections_valid",
        "menu_item_modifiers",
        "max_selections IS NULL OR (max_selections >= 1 AND max_selections >= min_selections)",
    )

    op.add_column(
        "modifier_options",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.drop_column("modifier_options", "sort_order")

    op.drop_constraint("ck_modifier_max_selections_valid", "menu_item_modifiers", type_="check")
    op.drop_constraint(
        "ck_modifier_min_selections_nonnegative", "menu_item_modifiers", type_="check"
    )
    op.add_column(
        "menu_item_modifiers",
        sa.Column("is_required", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute("UPDATE menu_item_modifiers SET is_required = min_selections > 0")
    op.drop_column("menu_item_modifiers", "sort_order")
    op.drop_column("menu_item_modifiers", "max_selections")
    op.drop_column("menu_item_modifiers", "min_selections")

    op.drop_constraint("fk_menu_items_category_id", "menu_items", type_="foreignkey")
    op.drop_index(op.f("ix_menu_items_category_id"), table_name="menu_items")
    op.drop_column("menu_items", "is_archived")
    op.drop_column("menu_items", "sort_order")
    op.drop_column("menu_items", "category_id")

    op.drop_index(op.f("ix_menu_categories_restaurant_id"), table_name="menu_categories")
    op.drop_table("menu_categories")
