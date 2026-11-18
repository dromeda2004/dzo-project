"""order cancellation: cancelled status, reason, note, timestamp

Revision ID: 75bea9e4303e
Revises: e244c811d626
Create Date: 2026-11-15

See docs/EPIC3_TRACKER.md epic3.task5 and open question 1. Postgres can add a value
to an enum but not remove one, so the downgrade rebuilds `order_status`, and it
refuses to run while any order is cancelled rather than guess what they become.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "75bea9e4303e"
down_revision: str | None = "e244c811d626"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

CANCELLATION_REASONS = (
    "ITEM_UNAVAILABLE",
    "CANNOT_FULFILL_REQUEST",
    "TOO_BUSY",
    "CLOSING",
    "OTHER",
)
ORDER_STATUSES_BEFORE = (
    "PLACED",
    "ACKNOWLEDGED",
    "OPEN_FOR_CLAIM",
    "CLAIMED",
    "READY_TIME_SET",
    "PICKED_UP",
    "DELIVERED",
)


def upgrade() -> None:
    # A new enum value can't be used in the transaction that adds it, and the check
    # constraint below uses it, so add it in its own committed block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'CANCELLED'")

    reason = sa.Enum(*CANCELLATION_REASONS, name="cancellation_reason")
    reason.create(op.get_bind())
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancellation_reason", reason, nullable=True))
    op.add_column("orders", sa.Column("cancellation_note", sa.String(length=500), nullable=True))
    op.create_check_constraint(
        "ck_orders_cancellation_complete",
        "orders",
        "(status = 'CANCELLED') = (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)",
    )


def downgrade() -> None:
    cancelled = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM orders WHERE status = 'CANCELLED'")
    )
    if cancelled:
        raise RuntimeError(
            f"{cancelled} order(s) are cancelled; there's no earlier status to move them "
            "to. Delete or update them by hand before downgrading."
        )

    op.drop_constraint("ck_orders_cancellation_complete", "orders", type_="check")
    op.drop_column("orders", "cancellation_note")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "cancelled_at")
    sa.Enum(name="cancellation_reason").drop(op.get_bind())

    # Rebuild order_status without CANCELLED. The status index is on the column, so
    # it's rebuilt automatically by the type change.
    op.execute("ALTER TYPE order_status RENAME TO order_status_old")
    sa.Enum(*ORDER_STATUSES_BEFORE, name="order_status").create(op.get_bind())
    op.execute(
        "ALTER TABLE orders ALTER COLUMN status TYPE order_status "
        "USING status::text::order_status"
    )
    op.execute("DROP TYPE order_status_old")
