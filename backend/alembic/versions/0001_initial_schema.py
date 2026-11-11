"""initial schema: assets, imports, transactions, corporate actions, payouts

Revision ID: 0001
Revises:
Create Date: 2026-11-11
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE assets (
          id          BIGSERIAL PRIMARY KEY,
          ticker      TEXT NOT NULL UNIQUE,
          name        TEXT,
          type        TEXT NOT NULL CHECK (type IN
                        ('stock','fii','fiagro','etf','crypto','fixed_income','treasury','currency','other')),
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE import_batches (
          id            BIGSERIAL PRIMARY KEY,
          source        TEXT NOT NULL CHECK (source IN ('trades','payouts')),
          filename      TEXT NOT NULL,
          imported_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
          rows_added    INT NOT NULL,
          rows_skipped  INT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE transactions (
          id               BIGSERIAL PRIMARY KEY,
          asset_id         BIGINT NOT NULL REFERENCES assets(id),
          trade_date       DATE NOT NULL,
          kind             TEXT NOT NULL CHECK (kind IN ('buy','sell')),
          quantity         NUMERIC(24,8) NOT NULL CHECK (quantity > 0),
          total_value      NUMERIC(18,2) NOT NULL CHECK (total_value >= 0),
          institution      TEXT,
          raw_ticker       TEXT NOT NULL,
          fingerprint      TEXT NOT NULL,
          occurrence       INT NOT NULL,
          import_batch_id  BIGINT REFERENCES import_batches(id),
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (fingerprint, occurrence)
        )
    """)

    op.execute("""
        CREATE TABLE corporate_actions (
          id              BIGSERIAL PRIMARY KEY,
          asset_id        BIGINT NOT NULL REFERENCES assets(id),
          action_date     DATE NOT NULL,
          kind            TEXT NOT NULL CHECK (kind IN ('split','reverse_split','bonus','fraction')),
          ratio_from      INT,
          ratio_to        INT,
          quantity        NUMERIC(24,8),
          cost_per_share  NUMERIC(18,6),
          cash_amount     NUMERIC(18,2),
          source_url      TEXT,
          note            TEXT,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE payouts (
          id               BIGSERIAL PRIMARY KEY,
          asset_id         BIGINT NOT NULL REFERENCES assets(id),
          pay_date         DATE NOT NULL,
          kind             TEXT NOT NULL CHECK (kind IN ('dividend','jcp','income','interest','other')),
          raw_event_type   TEXT NOT NULL,
          quantity_held    NUMERIC(24,8),
          net_amount       NUMERIC(18,2) NOT NULL,
          institution      TEXT,
          fingerprint      TEXT NOT NULL,
          occurrence       INT NOT NULL,
          import_batch_id  BIGINT REFERENCES import_batches(id),
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (fingerprint, occurrence)
        )
    """)

    op.execute("CREATE INDEX ix_transactions_asset_date ON transactions (asset_id, trade_date)")
    op.execute("CREATE INDEX ix_corporate_actions_asset_date ON corporate_actions (asset_id, action_date)")
    op.execute("CREATE INDEX ix_payouts_asset_date ON payouts (asset_id, pay_date)")


def downgrade() -> None:
    op.execute("DROP TABLE payouts")
    op.execute("DROP TABLE corporate_actions")
    op.execute("DROP TABLE transactions")
    op.execute("DROP TABLE import_batches")
    op.execute("DROP TABLE assets")
