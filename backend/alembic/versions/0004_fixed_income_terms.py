"""fixed_income_terms: the rule of each fixed income product (index, rate, maturity)

Purchases and redemptions are ordinary rows in `transactions`, interest is a row in
`payouts` (kind 'interest'). This table only holds what B3 does not report: the index and
rate the user knows from the bank. All fields are nullable and filled later.

Additive only.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fixed_income_terms (
          asset_id       BIGINT PRIMARY KEY REFERENCES assets(id),
          issuer         TEXT,
          index_name     TEXT CHECK (index_name IN ('cdi','selic','ipca','prefixed')),
          rate           NUMERIC(9,4),   -- cdi/selic: % of the index; ipca: spread % a.a.; prefixed: % a.a.
          maturity_date  DATE,
          note           TEXT,
          created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE fixed_income_terms")
