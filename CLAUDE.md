# Central de Investimentos

Rewrite of a personal investment tracking system, plus a daily "intelligence hub" that
collects documents about the owned assets and summarizes them with AI. This is the only
CLAUDE.md in the repo; topic docs live in `docs/` (read them on demand).

## Language
- Everything in the repository is in **English**: code, identifiers, comments, commit
  messages, docs, DB tables and columns.
- Portuguese appears **only in user-facing UI strings** (the user is Brazilian). Keep UI
  strings easy to extract: a bilingual UI (pt-BR/en) is planned.
- Exceptions: real B3 spreadsheet column names (e.g. `Código de Negociação`) and Brazilian
  terms with no good translation (FII, JCP, Tesouro Direto).
- Talk to the user in Portuguese.

## Goal
Two pillars, with one principle: **clear, verifiable data**. The user decides; the
system informs, summarizes and suggests, never orders.

1. **Refactor of the old system**: DB as source of truth, one command to run, easy to
   maintain, easy data entry.
2. **Report automation**: nightly collection of documents per asset, AI summaries with
   verifiable quotes, trend comparison, portfolio analysis with suggestions.

## Stack and running
- Backend: Python + FastAPI (`backend/`). Frontend: React + Vite + TS (`frontend/`).
- Database: PostgreSQL. Migrations: Alembic, hand-written SQL (no ORM). All in Docker Compose.
- Run: `docker compose up -d` (add `--build` only after changing a Dockerfile or
  `requirements.txt`). The API container applies pending migrations on startup.
  - Frontend: http://localhost:3000 (the Mac's port 5173 is used by another project)
  - API: http://localhost:8000/api/health | Postgres: localhost:5432
- The frontend calls `/api/...` and Vite proxies it to the API (no CORS).
- Quotes: brapi.dev free plan, token in `.env` as `BRAPI_TOKEN` (see `.env.example`,
  `docs/quotes.md`); the `worker` service refreshes them every 30 min in market hours.
- Hosting TBD (Railway charges after trial; free alternative: Neon/Supabase + Render/Fly).

## Project rules
- The database is the source of truth; `.xlsx` files are import input only.
- Derived data is never stored (average price, totals, distribution are computed).
- **History is never rewritten.** Corporate actions (splits, bonus, etc.) are separate
  events, not edits to past transactions (see `docs/corporate-actions.md`).
- Cost basis: **weighted average price** (standard for Brazilian income tax).
- Verifiable migration: new totals must match the old system; differences are explained.
- Every AI claim must be verifiable: original document link, hash, and a literal quote
  checked by code. Numbers come from structured data, never from the LLM.
- Suggestions are points of attention with sources, never investment advice.
- Fixed income is stored as a rule (index, rate, maturity); current value is computed
  from Central Bank (SGS) data and is an estimate the user can check against the bank.
- Money and quantities are `NUMERIC` (never float). Quantity needs decimals (Tesouro).
- `Ano`/`Mês` columns of the old spreadsheets are derived from the date, never stored.

## Data model (draft, not implemented)
| Table | Content |
|---|---|
| `assets` | ticker/name, type (stock, FII, Fiagro, Tesouro, CDB…) |
| `transactions` | date, asset, buy/sell, quantity, total value (not unit price) |
| `corporate_actions` | date, asset, kind (split, reverse split, bonus, fraction), ratio/amounts |
| `payouts` | date, asset, type (dividend, JCP, income), net amount |
| `fixed_income` | rule: index, rate, maturity, issuer, checked balance |
| `documents` | asset, type, date, original url, hash, extracted text |
| `summaries` | document, summary, pros/cons, quotes, verification status |

## Data sources (free)
CVM Open Data (material facts, ITR/DFP), Fundos.NET/B3 (FII reports; no good API),
brapi.dev/yfinance (quotes), Central Bank SGS (CDI, Selic, IPCA), Tesouro Transparente.

## AI and cost
- Claude Pro plan. Summaries run via headless `claude -p` on the user's Mac, at night,
  only for new documents; results go to Postgres.
- NEVER set `ANTHROPIC_API_KEY` (it would switch to per-token billing).
- Code does the heavy lifting (download, filter, extract text); the AI call lives behind
  one function (swappable for Ollama/Gemini).
- Zero cost; prefer open source. Hosted financial data requires authentication.

## Old system (reference only, DO NOT MODIFY)
- `../SpreadsheetInvestmentReader` (Python/FastAPI/pandas; rules in `Wallet.py`)
- `../InvestmentManagerInterface` (React/Vite)
- Read-only. All new code goes in this repository.

## Topic docs (`docs/`)
- `legacy-system-rules.md`: rules, bugs and data anomalies found in the old system.
- `database.md`: approved schema (DDL, decisions, open questions).
- `import.md`: design of the B3 file import (idempotent, preview, validations).
- `corporate-actions.md`: splits, reverse splits, bonus and fractions.
- `frontend.md`: frontend files and how the design plugs in.
- `quotes.md`: brapi quotes, token setup, valuation rules.
- `api.md`: read-only endpoints for the screens.
- `fixed-income.md`: CDB/LCA/Tesouro model, imported data, caveats.
- `payouts.md`: payouts import and the quantity cross-check against B3.
- `positions.md`: weighted average calculation, tests, comparison with the old system.

## Conventions
- Simplest solution first; no abstractions or dependencies without a real need.
- Small steps; verify each one before the next.
- Destructive operations (down -v, dropping tables, lossy migrations) need confirmation.
- Secrets only in `.env` (git-ignored).
- Test calculation rules (average price, corporate actions, fixed income) and quote
  verification first.
- The user makes the important engineering decisions: recommend, present alternatives.

## Open items
- Data anomalies are explained by the raw B3 files (see `docs/legacy-system-rules.md`).
  Only missing: cost per bonus share (company notices).
- The old spreadsheet is NOT a reliable import source (hand-edited rows). Raw B3 files
  (trades 2022-12 → 2026-09; payouts 2023-2026, one file per year) are in
  `backend/temp-data/` (git-ignored; never commit). Use them for the importer.
- Raw trades have no corporate events; they come from the B3 Movimentação report
  (`movimentacao-*.xlsx` in `backend/temp-data/`), which also has fixed income and
  position snapshots (`Atualização`). Details in `docs/import.md`.
- Raw payout files contain 1 repeated identical line (WEGE3 JCP 2025-12-12); keep both, as they
  come from B3 (occurrence counter).
- Fixed income: the B3 Movimentação report has Tesouro, 2 CDBs and 1 LCA (purchase,
  maturity, interest, units and unit price) but not the index/rate: the user supplies
  those once per product. Confirm no other fixed income lives outside B3.
- Authentication mechanism (single-user login is the simplest).
- Idea to adopt: validate computed positions against the `Quantidade` of each payout row.

## Roadmap
- [x] Skeleton: Docker Compose with db + api + web, verified end to end
- [x] Read `Wallet.py`, document legacy rules and data anomalies
- [x] Database schema drafted and approved (`docs/database.md`)
- [x] Alembic and first migration (`0001`, verified; see `docs/database.md`)
- [ ] B3 file importer, totals checked against the old system (trades import done and
      idempotent; positions by weighted average done and compared with the old system,
      see `docs/positions.md`; corporate events imported from Movimentação and applied;
      payouts imported and cross-checked, see `docs/payouts.md`;
      fixed income imported, see `docs/fixed-income.md`;
      next: bonus cost per share)
- [ ] Corporate actions (split, reverse split, bonus, fractions: imported and applied;
      KLBN transfers done; missing: bonus cost per share, manual entry form)
- [ ] Minimal API and screens (portfolio, totals, payouts): read-only API and brapi quotes done (verified with the real token: 21 of 21
      quotable positions), see `docs/api.md`, `docs/quotes.md`; automatic refresh (`worker`) done; frontend data layer and a plain home page
      done (`docs/frontend.md`); design "Main" (Tela 1) implemented
      with real data where it exists (`docs/frontend.md`); next: targets/sectors/history
- [ ] Fixed income module (import done; missing: index/rate, current value estimate)
- [ ] CVM collector (1 source, 1 asset) and document storage
- [ ] Summary with verified quotes (`claude -p`)
- [ ] Nightly scheduling (`launchd`) and digest
- [ ] Portfolio analysis with suggestions
- [ ] Authentication and hosting
- [ ] Bilingual UI (pt-BR/en)

## Living documentation
- When a feature is done: create/update a topic `.md` in `docs/` (what was done,
  decisions, how to use and verify) and tick the roadmap above.
- Keep this file under 200 lines; details go to `docs/`.
