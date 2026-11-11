# API (read-only, v1)

Code: `backend/app/routes.py`. Interactive docs with try-it-out: http://localhost:8000/docs.
The frontend calls `/api/...` (Vite proxies to the API). No authentication yet: local use
only (see open items in `CLAUDE.md`).

Everything is computed from the database on each request (nothing derived is stored).
Calculation uses `Decimal`; JSON carries plain numbers rounded for display (money 2 places,
average price 4, quantity 8). Names are English; dates are ISO (`2026-09-23`).

| Endpoint | Purpose |
|---|---|
| `GET /api/portfolio` | `totals` (invested, realized profit, payouts received, open positions), `by_type` (invested + share), `positions` (open ones: ticker, name, type, quantity, average_price, cost, share, warnings) |
| `GET /api/positions/{ticker}` | One asset: the position, a `timeline` of buys, sells and corporate events with `quantity_after`/`cost_after` (explains the number event by event), and its payouts. 404 if unknown |
| `GET /api/payouts?year=&ticker=` | Total, `by_month`, `by_kind`, `by_asset` and the `items` |
| `GET /api/transactions?ticker=&kind=buy\|sell&limit=&offset=` | Buys and sells, newest first, with `total` for paging (limit up to 500) |
| `GET /api/fixed-income` | CDB, LCA, Tesouro: bought, redeemed, interest received, units, `result` (redeemed + interest - bought, only when closed), rule (`index`, `rate`, `maturity_date`) and `terms_missing` |
| `GET /api/imports` | "Where did I stop": last date per source and the import history |
| `GET /api/data-quality` | Overall `status` and `checks` (payout quantities vs position, oversold positions, bonus cost known, fixed income terms) with `ok`/`attention` |

## Decisions
- Prices and current value are NOT here yet: they need a quotes source (brapi/yfinance).
  `invested` is the cost basis (weighted average), not market value.
- `positions` lists only open positions; closed ones are visible through `/api/positions/{ticker}`
  and their result is in `totals.realized_profit`.
- Fixed income `result` sums redemption and interest, because B3 reports them as two lines.
- Writing endpoints (upload, manual entry, fixed income terms) come with the upload screen.

## Verify
```
curl -s localhost:8000/api/portfolio | python3 -m json.tool | head -40
```
Real data today: invested 15,191.71 in 24 open positions; payouts received 2,915.63.
