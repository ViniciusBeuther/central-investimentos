"""Import the B3 'Proventos recebidos' exports (dividends, JCP, fund income).

Dry run, one or more files (also cross-checks B3's 'Quantidade' against the position):
    docker compose exec api python -W ignore -m app.importers.payouts "temp-data/proventos-*.xlsx"

Import for real:
    docker compose exec api python -W ignore -m app.importers.payouts temp-data/proventos-*.xlsx \
        --commit [--types temp-data/asset_types.json]

Re-importing the same or an overlapping file is safe: rows are recognized by
(fingerprint, occurrence). Identical repeated lines inside a file are all kept, as B3
gives them (occurrence counter).
"""
import argparse
import glob
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import psycopg
from openpyxl import load_workbook

from app.importers.trades import ASSET_TYPES, _canonical, _to_date, _to_decimal, suggest_type
from app.positions import compute_position
from app.positions_report import load_events

REQUIRED_COLUMNS = ["Produto", "Pagamento", "Tipo de Evento", "Instituição", "Quantidade", "Valor líquido"]
KINDS = {
    "Rendimento": "income",
    "Dividendo": "dividend",
    "Juros Sobre Capital Próprio": "jcp",
    "Juros": "interest",
}
TICKER_MARK = " - "  # 'BBAS3 - BANCO DO BRASIL S/A'; Tesouro has only its name
TOLERANCE = Decimal("0.0001")
LOOKBACK = timedelta(days=400)  # B3 counts the position at the record date, which can be long before payment


@dataclass(frozen=True)
class PayoutRow:
    pay_date: date
    ticker: str
    kind: str
    raw_event_type: str
    quantity_held: Decimal
    net_amount: Decimal
    institution: str
    fingerprint: str
    occurrence: int


def _quantity(value) -> Decimal:
    """B3 writes quantities as text: '7,28' (decimal comma) or '30'."""
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return Decimal(text)


def _ticker_of(product: str) -> str:
    return product.split(TICKER_MARK)[0].strip()


def parse_payouts_file(path: str) -> tuple[list[PayoutRow], list[str], Decimal | None]:
    """Return (rows, warnings, total declared by B3 at the end of the file)."""
    sheet = load_workbook(path, data_only=True).active  # not read_only, see trades.py
    lines = sheet.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(lines)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"Not a B3 payouts export, missing columns: {missing}")
    col = {name: header.index(name) for name in REQUIRED_COLUMNS}

    rows, warnings, declared_total = [], [], None
    seen: Counter = Counter()
    for line_number, line in enumerate(lines, start=2):
        product = str(line[col["Produto"]] or "").strip()
        if not product:
            # blank line, the 'Total' label, and the line with the declared total
            last = line[col["Valor líquido"]]
            if isinstance(last, (int, float)):
                declared_total = _to_decimal(last)
            continue

        raw_event = str(line[col["Tipo de Evento"]]).strip()
        kind = KINDS.get(raw_event)
        if kind is None:
            warnings.append(f"line {line_number}: unknown event type '{raw_event}' (stored as 'other')")
            kind = "other"
        ticker = _ticker_of(product)
        institution = str(line[col["Instituição"]]).strip()
        pay_date = _to_date(line[col["Pagamento"]])
        quantity = _quantity(line[col["Quantidade"]])
        net = _to_decimal(line[col["Valor líquido"]])
        if net <= 0:
            warnings.append(f"line {line_number}: {ticker} net amount {net}")

        fingerprint = hashlib.sha256(
            "|".join([pay_date.isoformat(), ticker, raw_event, _canonical(quantity), _canonical(net), institution]).encode()
        ).hexdigest()
        seen[fingerprint] += 1
        rows.append(PayoutRow(pay_date, ticker, kind, raw_event, quantity, net, institution, fingerprint, seen[fingerprint]))
    return rows, warnings, declared_total


# ---------------------------------------------------------------- asset types


def payout_type(ticker: str, chosen: dict[str, str]) -> str | None:
    if chosen.get(ticker):
        return chosen[ticker]
    if ticker.startswith("Tesouro"):
        return "treasury"
    return suggest_type(ticker)


# ---------------------------------------------------------------- cross-check


def broker_of(institution: str) -> str:
    """'XP INVESTIMENTOS CCTVM S/A.' and '... S/A' are the same broker; so are the two Nu names."""
    return institution.upper().split()[0]


def check_quantities(rows: list[PayoutRow], trades: dict, actions: dict) -> dict[str, list[tuple]]:
    """Compare B3's 'Quantidade' with the computed position at the payment date.

    B3 lists one line per brokerage, so quantities are summed ACROSS brokers (MXRF11 held
    at two brokers: 9 + 10 = 19). Identical repeated lines of the same broker (two
    payments declared for the same date) each repeat the full holding, so within a broker
    the quantity is counted once.

    B3's quantity is the holding at the RECORD date, which can be months before the payment
    (Klabin, Taesa and Sabesp pay long after). So a difference is "timing" when the
    computed position matched B3's number at some earlier moment in the last 400 days.

    Buckets of (ticker, pay_date, event, b3_quantity, computed_quantity):
    ok | timing (differs now, matched earlier) | suspect (never matched) | no_data
    (asset has no trades, e.g. Tesouro not imported yet).
    """
    per_broker: dict[tuple, Decimal] = {}
    for row in rows:
        key = (row.ticker, row.pay_date, row.raw_event_type, broker_of(row.institution))
        per_broker[key] = max(per_broker.get(key, Decimal(0)), row.quantity_held)
    grouped: dict[tuple, Decimal] = {}
    for (ticker, pay_date, event, _), quantity in per_broker.items():
        key = (ticker, pay_date, event)
        grouped[key] = grouped.get(key, Decimal(0)) + quantity

    buckets = {"ok": [], "timing": [], "suspect": [], "no_data": []}
    for (ticker, pay_date, event), b3_quantity in sorted(grouped.items()):
        asset_trades, asset_actions = trades.get(ticker, []), actions.get(ticker, [])
        if not asset_trades and not asset_actions:
            buckets["no_data"].append((ticker, pay_date, event, b3_quantity, None))
            continue
        position = compute_position(
            [t for t in asset_trades if t[0] <= pay_date],
            [a for a in asset_actions if a[0] <= pay_date],
        )
        item = (ticker, pay_date, event, b3_quantity, position.quantity)
        if abs(position.quantity - b3_quantity) <= TOLERANCE:
            buckets["ok"].append(item)
            continue
        start = pay_date - LOOKBACK
        moments = {start} | {e[0] for e in asset_trades + asset_actions if start < e[0] <= pay_date}
        matched_earlier = any(
            abs(compute_position(
                [t for t in asset_trades if t[0] <= moment], [a for a in asset_actions if a[0] <= moment]
            ).quantity - b3_quantity) <= TOLERANCE
            for moment in moments
        )
        buckets["timing" if matched_earlier else "suspect"].append(item)
    return buckets


# ---------------------------------------------------------------- database


def import_payouts(
    conn, rows: list[PayoutRow], filename: str, types: dict[str, str], source: str = "payouts"
) -> tuple[int, int]:
    """Write one file in ONE transaction. Returns (added, skipped). Caller commits."""
    asset_ids = {ticker: asset_id for ticker, asset_id in conn.execute("SELECT ticker, id FROM assets")}
    for ticker in sorted({r.ticker for r in rows} - asset_ids.keys()):
        if ticker not in types:
            raise ValueError(f"No type for new asset {ticker}")
        asset_ids[ticker] = conn.execute(
            "INSERT INTO assets (ticker, type) VALUES (%s, %s) RETURNING id", (ticker, types[ticker])
        ).fetchone()[0]

    batch_id = conn.execute(
        "INSERT INTO import_batches (source, filename, rows_added, rows_skipped) "
        "VALUES (%s, %s, 0, 0) RETURNING id",
        (source, filename),
    ).fetchone()[0]
    added = 0
    for r in rows:
        cursor = conn.execute(
            """
            INSERT INTO payouts
              (asset_id, pay_date, kind, raw_event_type, quantity_held, net_amount, institution,
               fingerprint, occurrence, import_batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fingerprint, occurrence) DO NOTHING
            """,
            (asset_ids[r.ticker], r.pay_date, r.kind, r.raw_event_type, r.quantity_held, r.net_amount,
             r.institution, r.fingerprint, r.occurrence, batch_id),
        )
        added += cursor.rowcount
    skipped = len(rows) - added
    conn.execute(
        "UPDATE import_batches SET rows_added = %s, rows_skipped = %s WHERE id = %s",
        (added, skipped, batch_id),
    )
    return added, skipped


# ---------------------------------------------------------------- command line


def main() -> None:
    parser = argparse.ArgumentParser(description="Import B3 'Proventos recebidos' exports")
    parser.add_argument("files", nargs="+", help="one or more .xlsx files (globs allowed)")
    parser.add_argument("--commit", action="store_true", help="write to the database")
    parser.add_argument("--types", help="JSON file {TICKER: type} for new assets")
    args = parser.parse_args()

    chosen = {}
    if args.types:
        with open(args.types) as f:
            chosen = json.load(f)
        bad = {t: k for t, k in chosen.items() if k not in ASSET_TYPES}
        if bad:
            raise SystemExit(f"Invalid asset types: {bad}")

    paths = sorted({p for pattern in args.files for p in (glob.glob(pattern) or [pattern])})
    parsed = {path: parse_payouts_file(path) for path in paths}

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        known = {r[0] for r in conn.execute("SELECT ticker FROM assets")}
        existing = {(r[0], r[1]) for r in conn.execute("SELECT fingerprint, occurrence FROM payouts")}
        all_rows, new_types, unresolved = [], {}, set()

        for path, (rows, warnings, declared) in parsed.items():
            total = sum(r.net_amount for r in rows)
            new = [r for r in rows if (r.fingerprint, r.occurrence) not in existing]
            repeated = sum(1 for r in rows if r.occurrence > 1)
            check = "no total in file" if declared is None else (
                "total matches B3" if abs(total - declared) <= Decimal("0.01") else f"TOTAL DIFFERS from B3 ({declared})"
            )
            print(f"{os.path.basename(path)}")
            print(f"  rows {len(rows)} ({min(r.pay_date for r in rows)} -> {max(r.pay_date for r in rows)}), "
                  f"net total {total:,.2f}: {check}")
            print(f"  new {len(new)}, already in database {len(rows) - len(new)}, repeated identical lines {repeated}")
            for w in warnings:
                print("  warning:", w)
            all_rows += rows
            for ticker in {r.ticker for r in rows} - known:
                kind = payout_type(ticker, chosen)
                if kind is None:
                    unresolved.add(ticker)
                else:
                    new_types[ticker] = kind

        if new_types:
            print("\nNew assets (from payouts only):", ", ".join(f"{t} ({k})" for t, k in sorted(new_types.items())))
        if unresolved:
            print("Need a type (pass --types):", ", ".join(sorted(unresolved)))

        by_kind = Counter(r.kind for r in all_rows)
        print(f"\nTotal rows {len(all_rows)}: " + ", ".join(f"{k} {n}" for k, n in sorted(by_kind.items())))

        trades, actions, _ = load_events(conn)
        buckets = check_quantities(all_rows, trades, actions)
        print("\nCross-check: B3 'Quantidade' (summed over brokers) vs computed position at payment date")
        print(f"  match            {len(buckets['ok']):4}")
        print(f"  differs, timing  {len(buckets['timing']):4}  (matched the position at an earlier date: record date)")
        print(f"  differs, SUSPECT {len(buckets['suspect']):4}  (nothing explains it)")
        print(f"  no data          {len(buckets['no_data']):4}  (asset without trades, e.g. Tesouro)")
        if buckets["suspect"]:
            print("  Suspects:")
            for ticker, pay_date, event, b3_quantity, computed in buckets["suspect"][:40]:
                print(f"    {pay_date} {ticker:8} {event[:12]:12} B3 says {b3_quantity}, computed {computed:.4f}")

        if not args.commit:
            print("\nDry run: nothing written. Add --commit to import.")
            return
        if unresolved:
            raise SystemExit("\nAborted: some new assets have no type. Nothing written.")
        for path, (rows, _, _) in parsed.items():
            added, skipped = import_payouts(conn, rows, os.path.basename(path), new_types)
            print(f"Imported {os.path.basename(path)}: {added} added, {skipped} skipped")
            known |= set(new_types)


if __name__ == "__main__":
    main()
