"""quotes: market prices fetched from an external source

External data, not derived data: each row is a price some source reported at some moment.
Kept as history (one row per quote time), the latest one is used for valuation.

Additive only.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE quotes (
          id          BIGSERIAL PRIMARY KEY,
          asset_id    BIGINT NOT NULL REFERENCES assets(id),
          price       NUMERIC(18,6) NOT NULL CHECK (price > 0),
          quoted_at   TIMESTAMPTZ NOT NULL,          -- when the market produced this price
          fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          source      TEXT NOT NULL,                 -- e.g. 'brapi'
          UNIQUE (asset_id, quoted_at, source)
        )
    """)
    op.execute("CREATE INDEX ix_quotes_asset_quoted ON quotes (asset_id, quoted_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE quotes")
