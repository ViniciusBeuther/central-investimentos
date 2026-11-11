# Payouts import (Proventos recebidos)

Code: `backend/app/importers/payouts.py`. Reads one or more B3 "Proventos recebidos" files.

```
# dry run: parse, totals, cross-check; writes nothing
docker compose exec api python -W ignore -m app.importers.payouts "temp-data/proventos-*.xlsx"
# import for real (add --types temp-data/asset_types.json if a new ticker needs a type)
docker compose exec api python -W ignore -m app.importers.payouts "temp-data/proventos-*.xlsx" --commit
```

## Rules
- Event types: `Rendimento` → income, `Dividendo` → dividend, `Juros Sobre Capital Próprio`
  → jcp, `Juros` → interest; anything else is stored as `other` with a warning. The raw
  text is kept in `raw_event_type`.
- `Quantidade` comes as text with a decimal comma (`'7,28'`); stored as `quantity_held`.
- The last three lines of each file (blank, `Total`, the total) are not payouts: the
  declared total is compared with the sum of the rows. All 4 files match.
- Idempotent like trades: `UNIQUE (fingerprint, occurrence)`. Fingerprint = date, ticker,
  event, quantity, net amount, institution. Re-run: 0 added.
- The Tesouro coupon ("Tesouro IPCA+ com Juros Semestrais 2055", 4 rows) creates the asset
  with type `treasury`; its name is its ticker.

## Result on the real files (2023-2026)
753 rows: 605 income, 87 dividend, 57 JCP, 4 interest. Net total per year: 225.40 (2023),
664.26 (2024), 968.85 (2025), 854.70 (2026). Only one repeated identical line exists
(WEGE3 JCP 0.95 on 2025-12-12, two equal declarations or a B3 duplicate; kept, occurrence 2).
The earlier note of "7 repeated lines" was wrong.

## Cross-check: B3 `Quantidade` vs computed position
This validates trades + corporate actions against B3's own data.
- B3 gives one line per broker (XP and Nu): quantities are summed across brokers (MXRF11
  9 + 10 = 19). `XP ... S/A` and `XP ... S/A.` are the same broker (first word). Repeated
  identical lines of one broker count once.
- B3's number is the holding at the **record date**, which can be months before payment
  (Klabin, Taesa, Sabesp). A difference is "timing" if the computed position matched B3's
  number at some moment in the previous 400 days.

| Result | Groups (asset, date, event) |
|---|---|
| Match at payment date | 604 |
| Differs, matches an earlier position (record date) | 53 |
| Suspect (never matched) | 2 |
| No data (Tesouro, no trades yet) | 4 |

The 2 suspects: BBAS3 `Rendimento` R$ 0.12 on 56 shares (tiny; the user has no stock lending, so the origin is unexplained, left open),
and TASA4 dividend 2026-06-15 where B3 still says 28 shares while the position is 30
(B3 payouts never reflected the 2025 bonus; all TASA4 payouts after it say 28).
