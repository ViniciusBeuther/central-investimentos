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
- Database: PostgreSQL. Migrations: Alembic (to be set up). All in Docker Compose.
- Run: `docker compose up -d --build`
  - Frontend: http://localhost:3000 (the Mac's port 5173 is used by another project)
  - API: http://localhost:8000/api/health | Postgres: localhost:5432
- The frontend calls `/api/...` and Vite proxies it to the API (no CORS).
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
- `import.md`: design of the B3 file import (idempotent, preview, validations).
- `corporate-actions.md`: splits, reverse splits, bonus and fractions.

## Conventions
- Simplest solution first; no abstractions or dependencies without a real need.
- Small steps; verify each one before the next.
- Destructive operations (down -v, dropping tables, lossy migrations) need confirmation.
- Secrets only in `.env` (git-ignored).
- Test calculation rules (average price, corporate actions, fixed income) and quote
  verification first.
- The user makes the important engineering decisions: recommend, present alternatives.

## Open items
- Data anomalies the user must verify against brokerage notes (details in
  `docs/legacy-system-rules.md`): CPTS11 x3 and BBAS3F `Valor`, Tesouro IPCA+ 2055
  `Preço`, TASA4F bonus, WEGE3 JCP duplicate.
- Fixed income: Tesouro appears in B3 files; CDB/LCI/LCA do not. Confirm which exist.
- Authentication mechanism (single-user login is the simplest).
- How past corporate actions (e.g. Americanas) were handled in the old spreadsheet.

## Roadmap
- [x] Skeleton: Docker Compose with db + api + web, verified end to end
- [x] Read `Wallet.py`, document legacy rules and data anomalies
- [ ] Draft database schema (user review), Alembic, first migration
- [ ] B3 file importer, totals checked against the old system
- [ ] Corporate actions (split, reverse split, bonus, fractions)
- [ ] Minimal API and screens (portfolio, totals, payouts)
- [ ] Fixed income module
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
