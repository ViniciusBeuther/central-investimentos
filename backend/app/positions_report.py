"""Print the current position of every asset, computed from the transactions.

    docker compose exec api python -W ignore -m app.positions_report [--csv]
"""
import argparse
import os
from collections import defaultdict
from decimal import Decimal

import psycopg

from app.positions import compute_position


def load_events(conn) -> tuple[dict, dict, dict]:
    """Return (trades, actions, types), each keyed by ticker, ready for compute_position."""
    trades, actions = defaultdict(list), defaultdict(list)
    types = {ticker: asset_type for ticker, asset_type in conn.execute("SELECT ticker, type FROM assets")}
    rows = conn.execute(
        "SELECT a.ticker, t.trade_date, t.kind, t.quantity, t.total_value "
        "FROM transactions t JOIN assets a ON a.id = t.asset_id"
    )
    for ticker, trade_date, kind, quantity, value in rows:
        trades[ticker].append((trade_date, kind, quantity, value))
    rows = conn.execute(
        "SELECT a.ticker, c.action_date, c.kind, c.quantity, c.cost_per_share, c.cash_amount "
        "FROM corporate_actions c JOIN assets a ON a.id = c.asset_id"
    )
    for ticker, action_date, kind, quantity, cost_per_share, cash in rows:
        actions[ticker].append((action_date, kind, quantity, cost_per_share, cash))
    return trades, actions, types


def load_positions(conn) -> list[tuple[str, str, object]]:
    """Return [(ticker, asset_type, Position)] sorted by ticker."""
    trades, actions, types = load_events(conn)
    return [(t, types[t], compute_position(trades[t], actions[t])) for t in sorted(set(trades) | set(actions))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Current positions (weighted average price)")
    parser.add_argument("--csv", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        positions = load_positions(conn)

    if args.csv:
        print("ticker,type,quantity,cost,average_price,realized_profit")
        for ticker, asset_type, p in positions:
            print(f"{ticker},{asset_type},{p.quantity:.8f},{p.cost:.2f},{p.average_price:.4f},{p.realized_profit:.2f}")
        return

    print(f"{'ticker':8} {'type':7} {'quantity':>12} {'cost':>10} {'avg price':>10} {'realized':>10}")
    total_cost = Decimal(0)
    total_realized = Decimal(0)
    for ticker, asset_type, p in positions:
        total_cost += p.cost
        total_realized += p.realized_profit
        note = "  (closed)" if p.quantity == 0 else ""
        print(f"{ticker:8} {asset_type:7} {p.quantity:12.4f} {p.cost:10.2f} {p.average_price:10.4f} {p.realized_profit:10.2f}{note}")
        for warning in p.warnings:
            print(f"         ! {warning}")
    print(f"\nTotal invested (cost of open positions): {total_cost:,.2f}")
    print(f"Total realized profit/loss:              {total_realized:,.2f}")


if __name__ == "__main__":
    main()
