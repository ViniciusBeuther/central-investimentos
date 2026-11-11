# Central de Investimentos

Rewrite of a personal investment tracking system, plus a daily "intelligence hub" that
collects documents about the owned assets and summarizes them with AI. Full details
(scope, requirements, decisions, roadmap) are in `docs/claude/CLAUDE.md`: read it on
demand, it is not loaded automatically.

## Language
- Everything in the repository is in **English**: code, identifiers, comments, commit
  messages, docs, DB tables and columns.
- Portuguese appears **only in user-facing UI strings** (the user is Brazilian). Keep UI
  strings easy to extract, since a bilingual UI (pt-BR/en) is planned for later.
- Exceptions: real data from B3 spreadsheets (column names like `Código de Negociação`)
  and Brazilian domain terms that have no good translation (e.g. FII, JCP, Tesouro Direto).

## Stack and running
- Backend: Python + FastAPI (`backend/`). Frontend: React + Vite + TS (`frontend/`).
- Database: PostgreSQL. Migrations: Alembic (to be set up). Everything in Docker Compose.
- Run: `docker compose up -d --build`
  - Frontend: http://localhost:3000 (the Mac's port 5173 is used by another project)
  - API: http://localhost:8000/api/health | Postgres: localhost:5432
- The frontend calls `/api/...` and Vite proxies it to the API (no CORS).

## Project rules
- The database is the source of truth; `.xlsx` spreadsheets are import input only.
- Derived data is never stored (average price, totals, distribution are computed).
- Verifiable migration: totals in the new system must match the old one.
- Every AI-produced claim must be verifiable: original document link, hash, and a
  literal quote checked by code. Numbers come from structured data, never from the LLM.
- Portfolio suggestions are points of attention with sources, never orders.
- Fixed income is stored as a rule (index, rate, maturity); the current value is computed.

## AI and cost
- Claude Pro plan. Summaries run via `claude -p` on the user's Mac, at night, only for
  new documents.
- NEVER set `ANTHROPIC_API_KEY` (it would switch to per-token billing).
- The AI call lives behind a single function (swappable for Ollama/Gemini).
- Zero cost; prefer open source.

## Old system (reference only, DO NOT MODIFY)
- `../SpreadsheetInvestmentReader` (Python/FastAPI/pandas; business rules in `Wallet.py`)
- `../InvestmentManagerInterface` (React/Vite)
- Read-only. All new code goes in this repository.

## Conventions
- Simplest solution first; no abstractions or dependencies without a real need.
- Small steps; verify each one before the next.
- Destructive operations (down -v, dropping tables, lossy migrations) need confirmation.
- Secrets only in `.env` (git-ignored). Hosted financial data requires login.
- Test calculation rules and quote verification first.
- Cost basis method: weighted average price.

## Living documentation
- When a feature is done: create/update a topic `.md` in `docs/claude/` (what was done,
  decisions, how to use and verify) and tick the roadmap (section 8 of
  `docs/claude/CLAUDE.md`).
- Keep this file under 200 lines; details go to `docs/claude/`.
