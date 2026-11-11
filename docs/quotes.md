# Quotes (market prices)

Code: `backend/app/quotes.py`, table `quotes` (migration `0005`), tests in
`backend/tests/test_quotes.py`.

## Source
**brapi.dev, free plan**: 15,000 requests/month, one ticker per call, token required.
Without a token only PETR4, VALE3, MGLU3 and ITUB4 answer. With ~24 open positions, a refresh
costs ~24 requests: even 10 refreshes a day stay near 7,000/month.
Why not yfinance: unofficial scraping of Yahoo, no published limits, known to break or
rate-limit; kept as the fallback idea. The source is behind ONE function (`fetch_quote`), so
swapping it touches nothing else.

## Setup (once)
1. Create a free account at https://brapi.dev and copy the token.
2. `cp .env.example .env`, then set `BRAPI_TOKEN=...` in `.env` (git-ignored; never commit it).
3. `docker compose up -d` (recreates the API with the token).

## Use
```
docker compose exec api python -W ignore -m app.quotes     # fetch and store now
curl -X POST localhost:8000/api/quotes/refresh             # same, from the screen (max once per 5 min)
```
Only open positions of stock, FII, Fiagro and ETF are quoted. Fixed income and Tesouro are
valued at cost (`valued_by: "cost"`) until the fixed income module computes a current value.

## Rules
- A quote is external data, not derived data, so it is stored with `source`, `quoted_at`
  (market time) and `fetched_at`. History is kept; the latest per asset is used.
- Failures are reported per ticker with a reason (token required, plan limit, not found,
  too many requests, network); one failure never blocks the others.
- Portfolio totals: `market_value` mixes quoted assets (price x quantity) and unquoted ones
  (cost). `unrealized_profit` counts quoted assets only, so cost does not look like a gain.
  `quotes_as_of` is the OLDEST quote time in use: the screen should show it.

## Verified
- Live call for PETR4 without token: price and market time parsed correctly.
- BBAS3 without token: clear "token required" failure.
- Valuation with a temporary quote: 58 x 25.00 = 1,450.00 vs cost 1,282.07 = +167.93 (the
  test row was deleted).

## Known limits
- Assets with unknown bonus cost (KLBN4, partly ALUP11, GGBR4, TASA4) show an inflated
  unrealized profit, because the bonus shares count as cost 0.
- The free plan may delay quotes; the screen shows `quoted_at` so the age is visible.

## Automatic refresh (worker)
`worker` service in `docker-compose.yml`, code in `backend/app/worker.py`, started by
`docker compose up -d` (restarts with Docker; one command still starts everything).
- Schedule (Brasília time, weekdays): every 30 minutes from 10:00 to 18:00 plus one run at
  18:30 for the closing price. About 17 runs x 21 assets a day, ~8,000 requests a month,
  inside the free plan's 15,000. Holidays are not special-cased (same quote time is stored once).
- Brasília is a fixed UTC-3 (no daylight saving since 2019), so no timezone database.
- Restart-safe: "is it due" is decided from `max(fetched_at)` in the database, so restarting
  the container never doubles a run. Errors are logged and the loop keeps going.
- Without `BRAPI_TOKEN` the worker only logs a warning. Logs: `docker compose logs -f worker`.
- Needs Docker running on the Mac. When hosted, the same service runs there.
- Tests: `backend/tests/test_worker.py` (window, weekends, UTC conversion, interval).
