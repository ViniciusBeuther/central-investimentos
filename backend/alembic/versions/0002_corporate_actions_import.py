"""corporate_actions can be imported idempotently from the Movimentação report

- fingerprint + occurrence + import_batch_id, like transactions and payouts
- import_batches accepts the 'movements' source

Additive only. The NOT NULL columns are safe because corporate_actions is still empty
(checked by the guard below; the migration aborts if it is not).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM corporate_actions) THEN
            RAISE EXCEPTION 'corporate_actions is not empty: cannot add NOT NULL columns';
          END IF;
        END $$
    """)
    op.execute("""
        ALTER TABLE corporate_actions
          ADD COLUMN fingerprint      TEXT   NOT NULL,
          ADD COLUMN occurrence       INT    NOT NULL,
          ADD COLUMN import_batch_id  BIGINT REFERENCES import_batches(id),
          ADD CONSTRAINT corporate_actions_fingerprint_occurrence_key UNIQUE (fingerprint, occurrence)
    """)
    op.execute("ALTER TABLE import_batches DROP CONSTRAINT import_batches_source_check")
    op.execute("""
        ALTER TABLE import_batches ADD CONSTRAINT import_batches_source_check
          CHECK (source IN ('trades','payouts','movements'))
    """)


def downgrade() -> None:
    # Lossy by nature: imported corporate actions lose their fingerprints and batch link.
    op.execute("""
        ALTER TABLE corporate_actions
          DROP CONSTRAINT corporate_actions_fingerprint_occurrence_key,
          DROP COLUMN import_batch_id,
          DROP COLUMN occurrence,
          DROP COLUMN fingerprint
    """)
    op.execute("DELETE FROM import_batches WHERE source = 'movements'")  # would violate the old check
    op.execute("ALTER TABLE import_batches DROP CONSTRAINT import_batches_source_check")
    op.execute("""
        ALTER TABLE import_batches ADD CONSTRAINT import_batches_source_check
          CHECK (source IN ('trades','payouts'))
    """)
