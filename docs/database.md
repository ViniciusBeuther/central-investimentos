# Database schema (APPROVED by the user; migration not created yet)

Scope of this draft: the portfolio core (assets, transactions, corporate actions, payouts,
imports). Fixed income, documents and summaries get their own tables when their features
are built, to avoid designing them blind.

## Migrations (Alembic)

Implemented in `backend/alembic/`; the first migration is `0001_initial_schema.py` and
creates the tables below. The project has no ORM models, so migrations are plain SQL via
`op.execute` and autogenerate is not used. `DATABASE_URL` comes from the environment.

The API container runs `alembic upgrade head` on every start (see `backend/Dockerfile`),
so `docker compose up -d` is enough; if a migration fails the container exits. Manual
commands, when needed:

```
docker compose exec api alembic upgrade head      # apply
docker compose exec api alembic current           # which version the DB is at
docker compose exec api alembic downgrade -1      # undo the last one (destroys its data)
```

New change = new file in `backend/alembic/versions/` (copy the pattern of `0001`); never
edit a migration that was already applied. Index names in the migration are explicit
(`ix_<table>_<columns>`); the DDL below leaves them unnamed for readability.

Verified in dev: tables created, duplicate `(fingerprint, occurrence)` rejected, a second
occurrence accepted, invalid asset `type` and `quantity = 0` rejected.

`backend/.dockerignore` keeps `temp-data/` (real financial files) out of the image.

## Principles
- Money is `NUMERIC(18,2)`, quantities are `NUMERIC(24,8)` (Tesouro has fractional bonds).
- Nothing derived is stored: positions, average price, totals and distribution are
  computed from `transactions` and `corporate_actions` (see "Position calculation").
- History is never edited. Corporate actions are separate rows.
- Every imported row keeps its fingerprint, so re-imports cannot duplicate it
  (see `import.md`).
- Raw B3 text is kept next to the interpreted value (`raw_ticker`, `raw_event_type`) so
  any interpretation can be audited and redone.

## Tables

```sql
CREATE TABLE assets (
  id          BIGSERIAL PRIMARY KEY,
  ticker      TEXT NOT NULL UNIQUE,      -- normalized: 'BBAS3', not 'BBAS3F'; Tesouro uses its name
  name        TEXT,
  type        TEXT NOT NULL CHECK (type IN
                ('stock','fii','fiagro','etf','crypto','fixed_income','treasury','currency','other')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE import_batches (
  id            BIGSERIAL PRIMARY KEY,
  source        TEXT NOT NULL CHECK (source IN ('trades','payouts')),
  filename      TEXT NOT NULL,
  imported_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  rows_added    INT NOT NULL,
  rows_skipped  INT NOT NULL
);

CREATE TABLE transactions (
  id               BIGSERIAL PRIMARY KEY,
  asset_id         BIGINT NOT NULL REFERENCES assets(id),
  trade_date       DATE NOT NULL,
  kind             TEXT NOT NULL CHECK (kind IN ('buy','sell')),
  quantity         NUMERIC(24,8) NOT NULL CHECK (quantity > 0),
  total_value      NUMERIC(18,2) NOT NULL CHECK (total_value >= 0),  -- whole operation, not unit price
  institution      TEXT,
  raw_ticker       TEXT NOT NULL,        -- as in the file, e.g. 'BBAS3F'
  fingerprint      TEXT NOT NULL,
  occurrence       INT  NOT NULL,        -- 1st, 2nd... identical row in the same file
  import_batch_id  BIGINT REFERENCES import_batches(id),  -- NULL = manual entry
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (fingerprint, occurrence)
);

CREATE TABLE corporate_actions (
  id              BIGSERIAL PRIMARY KEY,
  asset_id        BIGINT NOT NULL REFERENCES assets(id),
  action_date     DATE NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('split','reverse_split','bonus','fraction')),
  ratio_from      INT,                    -- split 1 -> 2 : from=1, to=2 (also reverse split)
  ratio_to        INT,
  quantity        NUMERIC(24,8),          -- bonus: shares received; fraction: fraction removed
  cost_per_share  NUMERIC(18,6),          -- bonus: cost declared by the company
  cash_amount     NUMERIC(18,2),          -- fraction auction cash
  source_url      TEXT,                   -- official notice, for verifiability
  note            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payouts (
  id               BIGSERIAL PRIMARY KEY,
  asset_id         BIGINT NOT NULL REFERENCES assets(id),
  pay_date         DATE NOT NULL,
  kind             TEXT NOT NULL CHECK (kind IN ('dividend','jcp','income','interest','other')),
  raw_event_type   TEXT NOT NULL,         -- e.g. 'Juros Sobre Capital Próprio'
  quantity_held    NUMERIC(24,8),         -- B3's 'Quantidade': used to cross-check positions
  net_amount       NUMERIC(18,2) NOT NULL,
  institution      TEXT,
  fingerprint      TEXT NOT NULL,
  occurrence       INT  NOT NULL,
  import_batch_id  BIGINT REFERENCES import_batches(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (fingerprint, occurrence)
);

CREATE INDEX ON transactions (asset_id, trade_date);
CREATE INDEX ON corporate_actions (asset_id, action_date);
CREATE INDEX ON payouts (asset_id, pay_date);
```

## Decisions to review

1. **Fractional ticker `F` is stripped** (`BBAS3F` → asset `BBAS3`); the original stays in
   `raw_ticker`. The old system treated them via string tricks.
2. **`Bonificacao` rows from the trades file go to `corporate_actions`** (kind `bonus`),
   not to `transactions`, because a bonus is not a purchase.
3. **No stored type heuristics**: `assets.type` is filled once, when a new ticker first
   appears (the importer asks).
4. **Position calculation lives in application code**, not in SQL: one tested function
   walks transactions and corporate actions by date and returns quantity, total cost and
   weighted average price. A SQL view can be added later if a screen needs it.
5. **`UNIQUE (fingerprint, occurrence)`** is the last-resort duplicate guard.
6. **Deleting an import** = delete rows by `import_batch_id` (with user confirmation).

## Open questions
- (Decided) Same-date ordering: a corporate action takes effect at the **start of its
  effective date**, before trades of that day (the usual ex-date convention: trades from
  the ex-date on are already in post-event units and prices). Validated by the payout
  `Quantidade` cross-check; revisit if a real case contradicts it.
- (Decided) Asset type: tickers ending in 11 are ambiguous (FII, Fiagro, ETF, unit), so
  the importer **suggests** a type (from the FII/Fiagro lists in the old project's
  `assets/`, read-only) and the user confirms once. Types: stock, fii, fiagro, etf,
  crypto, fixed_income, treasury, currency, other.
- Crypto and currency (USD) do not come from B3 files: they start as manual entries.
  They will need a `currency` column on transactions (BRL/USD); not added until the
  feature is built.
- Tesouro: stored as an asset with its bond name as ticker. Revisit when the fixed income
  module is designed.
