"""Market quotes from an external source (brapi.dev, free plan).

    docker compose exec api python -W ignore -m app.quotes          # fetch and store

The source sits behind ONE function, `fetch_quote`, so it can be swapped (yfinance, another
API) without touching the rest. The token comes from the BRAPI_TOKEN environment variable
(set it in `.env`, never in code). Without a token only PETR4, VALE3, MGLU3 and ITUB4 work.

Only assets with an open position and a market price are quoted: stocks, FII, Fiagro, ETF.
Fixed income and Tesouro have no market quote here (valued at cost until that module exists).
"""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import psycopg

from app.positions import compute_position
from app.positions_report import load_events

SOURCE = "brapi"
URL = "https://brapi.dev/api/quote/{ticker}"
QUOTED_TYPES = ("stock", "fii", "fiagro", "etf")
PAUSE_SECONDS = 0.3  # the free plan takes one ticker per call; be gentle


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: Decimal
    quoted_at: datetime
    source: str = SOURCE


def parse_brapi(ticker: str, payload: dict) -> Quote:
    """Pure parsing of a brapi response. Raises ValueError if it has no usable price."""
    results = payload.get("results") or []
    if not results:
        raise ValueError("no results")
    item = results[0]
    price, when = item.get("regularMarketPrice"), item.get("regularMarketTime")
    if price is None or when is None:
        raise ValueError("response without price or time")
    price = Decimal(str(price))
    if price <= 0:
        raise ValueError(f"invalid price {price}")
    return Quote(ticker, price, datetime.fromisoformat(when.replace("Z", "+00:00")))


def fetch_quote(ticker: str, token: str | None = None) -> Quote:
    """The one function that talks to the outside. Raises on any failure, with a clear reason."""
    request = urllib.request.Request(URL.format(ticker=ticker), headers={"Accept": "application/json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return parse_brapi(ticker, json.load(response))
    except urllib.error.HTTPError as error:
        reasons = {401: "token required or invalid", 402: "plan limit reached", 404: "ticker not found",
                   429: "too many requests"}
        raise RuntimeError(reasons.get(error.code, f"HTTP {error.code}")) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"network error: {error}") from error


def quotable_tickers(conn) -> list[str]:
    """Open positions of types that have a market price."""
    trades, actions, _ = load_events(conn)
    types = dict(conn.execute("SELECT ticker, type FROM assets"))
    return [
        t for t in sorted(set(trades) | set(actions))
        if types[t] in QUOTED_TYPES and compute_position(trades[t], actions[t]).quantity > Decimal("0.00000001")
    ]


def save_quotes(conn, quotes: list[Quote]) -> int:
    """Store quotes; the same (asset, quote time, source) is never stored twice."""
    ids = dict(conn.execute("SELECT ticker, id FROM assets"))
    added = 0
    for q in quotes:
        added += conn.execute(
            "INSERT INTO quotes (asset_id, price, quoted_at, source) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (asset_id, quoted_at, source) DO NOTHING",
            (ids[q.ticker], q.price, q.quoted_at, q.source),
        ).rowcount
    return added


def refresh(conn, tickers: list[str] | None = None, token: str | None = None) -> tuple[list[Quote], dict[str, str]]:
    """Fetch and store. Returns (quotes fetched, {ticker: reason} for the ones that failed)."""
    tickers = tickers if tickers is not None else quotable_tickers(conn)
    quotes, failures = [], {}
    for ticker in tickers:
        try:
            quotes.append(fetch_quote(ticker, token))
        except (RuntimeError, ValueError) as error:
            failures[ticker] = str(error)
        time.sleep(PAUSE_SECONDS)
    save_quotes(conn, quotes)
    return quotes, failures


def latest_quotes(conn) -> dict[str, tuple[Decimal, datetime]]:
    """{ticker: (price, quoted_at)} using the most recent quote of each asset."""
    rows = conn.execute(
        "SELECT DISTINCT ON (q.asset_id) a.ticker, q.price, q.quoted_at FROM quotes q "
        "JOIN assets a ON a.id = q.asset_id ORDER BY q.asset_id, q.quoted_at DESC"
    )
    return {ticker: (price, quoted_at) for ticker, price, quoted_at in rows}


def main() -> None:
    token = os.environ.get("BRAPI_TOKEN") or None
    print("Token:", "set" if token else "NOT set (only PETR4, VALE3, MGLU3, ITUB4 will work)")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        quotes, failures = refresh(conn, token=token)
    print(f"Fetched {len(quotes)} quotes at {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    for q in quotes:
        print(f"  {q.ticker:8} {q.price:>10}  (market time {q.quoted_at:%Y-%m-%d %H:%M} UTC)")
    for ticker, reason in failures.items():
        print(f"  {ticker:8} FAILED: {reason}")


if __name__ == "__main__":
    main()
