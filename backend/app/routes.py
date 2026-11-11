"""Read-only API for the screens. Everything is computed from the database on request.

Numbers are sent as JSON numbers (rounded for display). The calculation itself stays in
Decimal (see positions.py): floats only appear at the very edge, in `num()`.
"""
import os
from collections import defaultdict
from decimal import Decimal

import psycopg
from fastapi import APIRouter, HTTPException, Query

from app.importers.payouts import PayoutRow, check_quantities
from app.positions import compute_position
from app.positions_report import load_events

router = APIRouter(prefix="/api")

DATABASE_URL = os.environ["DATABASE_URL"]
ZERO = Decimal(0)
EPSILON = Decimal("0.00000001")


def connect():
    return psycopg.connect(DATABASE_URL)


def num(value, places: int = 2) -> float | None:
    return None if value is None else round(float(value), places)


def _asset_info(conn) -> dict[str, dict]:
    return {
        ticker: {"name": name, "type": asset_type}
        for ticker, name, asset_type in conn.execute("SELECT ticker, name, type FROM assets")
    }


def _positions(conn):
    """[(ticker, info, Position)] for every asset that has trades or corporate actions."""
    trades, actions, _ = load_events(conn)
    info = _asset_info(conn)
    return [
        (t, info[t], compute_position(trades[t], actions[t])) for t in sorted(set(trades) | set(actions))
    ]


def _position_json(ticker: str, info: dict, p) -> dict:
    return {
        "ticker": ticker,
        "name": info["name"],
        "type": info["type"],
        "quantity": num(p.quantity, 8),
        "average_price": num(p.average_price, 4),
        "cost": num(p.cost),
        "realized_profit": num(p.realized_profit),
        "warnings": p.warnings,
    }


# ---------------------------------------------------------------- portfolio


@router.get("/portfolio")
def portfolio():
    """Open positions, totals and the distribution by asset type."""
    with connect() as conn:
        positions = _positions(conn)
        payouts_total = conn.execute("SELECT COALESCE(SUM(net_amount), 0) FROM payouts").fetchone()[0]

    open_positions = [(t, i, p) for t, i, p in positions if p.quantity > EPSILON]
    invested = sum((p.cost for _, _, p in open_positions), ZERO)
    by_type = defaultdict(lambda: ZERO)
    for _, info, p in open_positions:
        by_type[info["type"]] += p.cost

    return {
        "totals": {
            "invested": num(invested),
            "realized_profit": num(sum((p.realized_profit for _, _, p in positions), ZERO)),
            "payouts_received": num(payouts_total),
            "open_positions": len(open_positions),
        },
        "by_type": [
            {"type": t, "invested": num(c), "share": num(c / invested, 4) if invested else 0}
            for t, c in sorted(by_type.items(), key=lambda kv: -kv[1])
        ],
        "positions": [
            {**_position_json(t, i, p), "share": num(p.cost / invested, 4) if invested else 0}
            for t, i, p in sorted(open_positions, key=lambda x: -x[2].cost)
        ],
    }


@router.get("/positions/{ticker}")
def position_detail(ticker: str):
    """One asset: the position and the timeline that explains it, event by event."""
    with connect() as conn:
        trades, actions, _ = load_events(conn)
        info = _asset_info(conn)
        if ticker not in info:
            raise HTTPException(404, f"Unknown asset {ticker}")
        payouts = conn.execute(
            "SELECT p.pay_date, p.kind, p.net_amount, p.quantity_held FROM payouts p "
            "JOIN assets a ON a.id = p.asset_id WHERE a.ticker = %s ORDER BY p.pay_date",
            (ticker,),
        ).fetchall()

    # Same-day order as in compute_position: actions, buys, sells.
    events = [(a[0], 0, "action", a) for a in actions[ticker]]
    events += [(t[0], 1 if t[1] == "buy" else 2, "trade", t) for t in trades[ticker]]
    events.sort(key=lambda e: (e[0], e[1]))
    timeline = []
    for i, (event_date, _, source, event) in enumerate(events):
        prefix = events[: i + 1]
        after = compute_position(
            [e[3] for e in prefix if e[2] == "trade"], [e[3] for e in prefix if e[2] == "action"]
        )
        if source == "trade":
            item = {"type": event[1], "quantity": num(event[2], 8), "value": num(event[3])}
        else:
            item = {"type": event[1], "quantity": num(event[2], 8), "cash": num(event[4])}
        timeline.append({"date": event_date.isoformat(), **item,
                         "quantity_after": num(after.quantity, 8), "cost_after": num(after.cost)})

    position = compute_position(trades[ticker], actions[ticker])
    return {
        "position": _position_json(ticker, info[ticker], position),
        "timeline": timeline,
        "payouts": [
            {"date": d.isoformat(), "kind": k, "net_amount": num(n), "quantity_held": num(q, 8)}
            for d, k, n, q in payouts
        ],
        "payouts_total": num(sum((p[2] for p in payouts), ZERO)),
    }


# ---------------------------------------------------------------- payouts


@router.get("/payouts")
def payouts(year: int | None = Query(None, ge=2000, le=2100), ticker: str | None = None):
    """Payouts with totals by month, kind and asset. Filter by year and/or ticker."""
    sql = (
        "SELECT p.pay_date, a.ticker, p.kind, p.net_amount FROM payouts p "
        "JOIN assets a ON a.id = p.asset_id WHERE true"
    )
    params: list = []
    if year:
        sql += " AND date_part('year', p.pay_date) = %s"
        params.append(year)
    if ticker:
        sql += " AND a.ticker = %s"
        params.append(ticker)
    with connect() as conn:
        rows = conn.execute(sql + " ORDER BY p.pay_date DESC, a.ticker", params).fetchall()

    by_month, by_kind, by_asset = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for pay_date, asset, kind, net in rows:
        by_month[pay_date.strftime("%Y-%m")] += net
        by_kind[kind] += net
        by_asset[asset] += net
    return {
        "total": num(sum((r[3] for r in rows), ZERO)),
        "count": len(rows),
        "by_month": [{"month": m, "total": num(v)} for m, v in sorted(by_month.items())],
        "by_kind": [{"kind": k, "total": num(v)} for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])],
        "by_asset": [{"ticker": t, "total": num(v)} for t, v in sorted(by_asset.items(), key=lambda kv: -kv[1])],
        "items": [
            {"date": d.isoformat(), "ticker": t, "kind": k, "net_amount": num(n)} for d, t, k, n in rows
        ],
    }


# ---------------------------------------------------------------- transactions


@router.get("/transactions")
def transactions(
    ticker: str | None = None,
    kind: str | None = Query(None, pattern="^(buy|sell)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Buys and sells, newest first."""
    where, params = "WHERE true", []
    if ticker:
        where += " AND a.ticker = %s"
        params.append(ticker)
    if kind:
        where += " AND t.kind = %s"
        params.append(kind)
    base = f"FROM transactions t JOIN assets a ON a.id = t.asset_id {where}"
    with connect() as conn:
        total = conn.execute(f"SELECT count(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT t.trade_date, a.ticker, t.kind, t.quantity, t.total_value, t.institution {base} "
            "ORDER BY t.trade_date DESC, t.id DESC LIMIT %s OFFSET %s",
            params + [limit, offset],
        ).fetchall()
    return {
        "total": total,
        "items": [
            {"date": d.isoformat(), "ticker": t, "kind": k, "quantity": num(q, 8), "value": num(v),
             "institution": inst}
            for d, t, k, q, v, inst in rows
        ],
    }


# ---------------------------------------------------------------- fixed income


@router.get("/fixed-income")
def fixed_income():
    """CDB, LCA and Tesouro: what was put in, what came back, and the product's rule."""
    with connect() as conn:
        products = conn.execute(
            """
            SELECT a.ticker, a.name, a.type, f.issuer, f.index_name, f.rate, f.maturity_date,
                   COALESCE(SUM(t.total_value) FILTER (WHERE t.kind = 'buy'), 0),
                   COALESCE(SUM(t.total_value) FILTER (WHERE t.kind = 'sell'), 0),
                   COALESCE(SUM(t.quantity) FILTER (WHERE t.kind = 'buy'), 0)
                     - COALESCE(SUM(t.quantity) FILTER (WHERE t.kind = 'sell'), 0)
            FROM assets a
            LEFT JOIN fixed_income_terms f ON f.asset_id = a.id
            LEFT JOIN transactions t ON t.asset_id = a.id
            WHERE a.type IN ('fixed_income', 'treasury')
            GROUP BY a.id, f.asset_id ORDER BY a.ticker
            """
        ).fetchall()
        interest = dict(conn.execute(
            "SELECT a.ticker, SUM(p.net_amount) FROM payouts p JOIN assets a ON a.id = p.asset_id "
            "WHERE a.type IN ('fixed_income', 'treasury') GROUP BY a.ticker"
        ).fetchall())

    items = []
    for ticker, name, asset_type, issuer, index_name, rate, maturity, bought, redeemed, quantity in products:
        received = interest.get(ticker, ZERO)
        closed = quantity <= EPSILON
        items.append({
            "ticker": ticker, "name": name, "type": asset_type, "issuer": issuer,
            "index": index_name, "rate": num(rate, 4), "maturity_date": maturity.isoformat() if maturity else None,
            "status": "closed" if closed else "open",
            "units": num(quantity, 8),
            "bought": num(bought), "redeemed": num(redeemed), "interest_received": num(received),
            # Redemption and interest are separate B3 lines: the real result is their sum.
            "result": num(redeemed + received - bought) if closed else None,
            "terms_missing": index_name is None or rate is None,
        })
    return {"items": items}


# ---------------------------------------------------------------- imports and data quality


@router.get("/imports")
def imports():
    """Where did I stop: last date per source and the import history."""
    with connect() as conn:
        last = {
            "trades": conn.execute("SELECT max(trade_date) FROM transactions").fetchone()[0],
            "payouts": conn.execute("SELECT max(pay_date) FROM payouts").fetchone()[0],
            "corporate_actions": conn.execute("SELECT max(action_date) FROM corporate_actions").fetchone()[0],
        }
        batches = conn.execute(
            "SELECT id, source, filename, imported_at, rows_added, rows_skipped "
            "FROM import_batches ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return {
        "last_dates": {k: v.isoformat() if v else None for k, v in last.items()},
        "batches": [
            {"id": i, "source": s, "filename": f, "imported_at": at.isoformat(), "added": a, "skipped": k}
            for i, s, f, at, a, k in batches
        ],
    }


@router.get("/data-quality")
def data_quality():
    """Checks that tell whether the numbers can be trusted. 'attention' = look at it."""
    with connect() as conn:
        positions = _positions(conn)
        trades, actions, _ = load_events(conn)
        payout_rows = [
            PayoutRow(d, t, "other", e, q, n, inst, "", 1)
            for t, d, e, q, n, inst in conn.execute(
                "SELECT a.ticker, p.pay_date, p.raw_event_type, p.quantity_held, p.net_amount, p.institution "
                "FROM payouts p JOIN assets a ON a.id = p.asset_id"
            )
        ]
        unknown_cost = conn.execute(
            "SELECT count(*) FROM corporate_actions WHERE kind IN ('bonus','transfer_in') AND cost_per_share IS NULL"
        ).fetchone()[0]
        terms_missing = conn.execute(
            "SELECT count(*) FROM fixed_income_terms WHERE index_name IS NULL OR rate IS NULL"
        ).fetchone()[0]

    buckets = check_quantities(payout_rows, trades, actions)
    oversold = [(t, w) for t, _, p in positions for w in p.warnings if w.split(": ", 1)[1].startswith(("sold", "fraction", "transfer out"))]
    checks = [
        {"name": "payout_quantities", "status": "attention" if buckets["suspect"] else "ok",
         "detail": f"{len(buckets['ok'])} match, {len(buckets['timing'])} match an earlier position, "
                   f"{len(buckets['suspect'])} suspect, {len(buckets['no_data'])} without data",
         "items": [f"{t} {d} B3 {b3:.4f} vs computed {c:.4f}" for t, d, _, b3, c in buckets["suspect"]]},
        {"name": "no_oversold_positions", "status": "attention" if oversold else "ok",
         "detail": f"{len(oversold)} sales or fractions larger than the position",
         "items": [f"{t}: {w}" for t, w in oversold]},
        {"name": "bonus_cost_known", "status": "attention" if unknown_cost else "ok",
         "detail": f"{unknown_cost} bonus or transfer events without cost per share (counted as 0)", "items": []},
        {"name": "fixed_income_terms", "status": "attention" if terms_missing else "ok",
         "detail": f"{terms_missing} fixed income products without index/rate", "items": []},
    ]
    return {"status": "attention" if any(c["status"] != "ok" for c in checks) else "ok", "checks": checks}
