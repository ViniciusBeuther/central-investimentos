"""corporate_actions accepts transfer_out / transfer_in (asset conversions)

B3 'Transferência' moves quantity from one ticker to others (KLBN11 -> KLBN3 + KLBN4).
Each side is its own row: a debit on the origin, a credit on each destination.

Relaxes a CHECK constraint only; existing rows stay valid.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE corporate_actions DROP CONSTRAINT corporate_actions_kind_check")
    op.execute("""
        ALTER TABLE corporate_actions ADD CONSTRAINT corporate_actions_kind_check
          CHECK (kind IN ('split','reverse_split','bonus','fraction','transfer_out','transfer_in'))
    """)


def downgrade() -> None:
    # Lossy: transfers cannot be kept under the old constraint.
    op.execute("DELETE FROM corporate_actions WHERE kind IN ('transfer_out','transfer_in')")
    op.execute("ALTER TABLE corporate_actions DROP CONSTRAINT corporate_actions_kind_check")
    op.execute("""
        ALTER TABLE corporate_actions ADD CONSTRAINT corporate_actions_kind_check
          CHECK (kind IN ('split','reverse_split','bonus','fraction'))
    """)
