"""Import the B3 'Negociação' export.

Dry run (reads and validates, writes nothing):
    docker compose exec api python -W ignore -m app.importers.trades "temp-data/<file>.xlsx"

Import for real (needs a type for every new asset, see --types):
    docker compose exec api python -W ignore -m app.importers.trades "temp-data/<file>.xlsx" \
        --commit --types temp-data/asset_types.json

Importing the same or an overlapping file again is safe: rows already in the database
are recognized by (fingerprint, occurrence) and skipped.
"""
import argparse
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import psycopg
from openpyxl import load_workbook

REQUIRED_COLUMNS = [
    "Data do Negócio",
    "Tipo de Movimentação",
    "Mercado",
    "Instituição",
    "Código de Negociação",
    "Quantidade",
    "Preço",
    "Valor",
]
KINDS = {"Compra": "buy", "Venda": "sell"}
FRACTIONAL_MARKET = "Mercado Fracionário"
ASSET_TYPES = {"stock", "fii", "fiagro", "etf", "crypto", "fixed_income", "treasury", "currency", "other"}


@dataclass(frozen=True)
class TradeRow:
    trade_date: date
    kind: str  # 'buy' | 'sell'
    ticker: str  # normalized, e.g. 'BBAS3'
    raw_ticker: str  # as in the file, e.g. 'BBAS3F'
    quantity: Decimal
    total_value: Decimal  # whole operation, not unit price
    institution: str
    fingerprint: str
    occurrence: int  # 1st, 2nd... identical row in the same file


# ---------------------------------------------------------------- parsing (no database)


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip(), "%d/%m/%Y").date()


def _to_decimal(value) -> Decimal:
    # str() first: Decimal(0.1) would carry binary float noise, Decimal("0.1") does not.
    return Decimal(str(value).strip())


def _canonical(number: Decimal) -> str:
    """'10', '10.0' and '10.00' must produce the same fingerprint."""
    return format(number.normalize(), "f")


def _normalize_ticker(raw_ticker: str, market: str) -> str:
    # The fractional market appends an 'F' (BBAS3 -> BBAS3F). Strip it only there, so a
    # real ticker that happens to end in F is never touched.
    if market == FRACTIONAL_MARKET and raw_ticker.endswith("F"):
        return raw_ticker[:-1]
    return raw_ticker


def parse_trades_file(path: str) -> tuple[list[TradeRow], list[str]]:
    """Return (rows, warnings). Raises ValueError if the file is not a B3 trades export."""
    # Not read_only: B3 files do not declare their dimensions, and read_only mode then
    # returns only the first column. The files are small, so loading them fully is fine.
    workbook = load_workbook(path, data_only=True)
    sheet = workbook.active
    lines = sheet.iter_rows(values_only=True)

    header = [str(cell).strip() if cell is not None else "" for cell in next(lines)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"Not a B3 trades export, missing columns: {missing}")
    col = {name: header.index(name) for name in REQUIRED_COLUMNS}

    rows: list[TradeRow] = []
    warnings: list[str] = []
    seen: Counter = Counter()

    for line_number, line in enumerate(lines, start=2):
        if all(cell is None for cell in line):
            continue

        movement = str(line[col["Tipo de Movimentação"]]).strip()
        if movement not in KINDS:
            warnings.append(f"line {line_number}: unknown movement type '{movement}' (skipped)")
            continue

        trade_date = _to_date(line[col["Data do Negócio"]])
        raw_ticker = str(line[col["Código de Negociação"]]).strip()
        market = str(line[col["Mercado"]]).strip()
        institution = str(line[col["Instituição"]]).strip()
        quantity = _to_decimal(line[col["Quantidade"]])
        unit_price = _to_decimal(line[col["Preço"]])
        total_value = _to_decimal(line[col["Valor"]])
        kind = KINDS[movement]

        if abs(quantity * unit_price - total_value) > Decimal("0.05"):
            warnings.append(
                f"line {line_number}: {raw_ticker} value {total_value} != "
                f"quantity {quantity} x price {unit_price}"
            )
        if kind == "sell" and total_value == 0:
            warnings.append(f"line {line_number}: {raw_ticker} sale with value 0")

        fingerprint = hashlib.sha256(
            "|".join(
                [
                    trade_date.isoformat(),
                    raw_ticker,
                    kind,
                    _canonical(quantity),
                    _canonical(total_value),
                    institution,
                ]
            ).encode()
        ).hexdigest()
        seen[fingerprint] += 1

        rows.append(
            TradeRow(
                trade_date=trade_date,
                kind=kind,
                ticker=_normalize_ticker(raw_ticker, market),
                raw_ticker=raw_ticker,
                quantity=quantity,
                total_value=total_value,
                institution=institution,
                fingerprint=fingerprint,
                occurrence=seen[fingerprint],
            )
        )

    return rows, warnings


# ---------------------------------------------------------------- asset types


def suggest_type(ticker: str) -> str | None:
    """Only the unambiguous cases. Tickers ending in 11 can be FII, Fiagro, ETF or unit."""
    if re.fullmatch(r"[A-Z]{4}[3-6]", ticker):
        return "stock"
    return None


def resolve_types(new_tickers: list[str], chosen: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Return ({ticker: type}, tickers still without a type). Never guesses."""
    types, unresolved = {}, []
    for ticker in new_tickers:
        asset_type = chosen.get(ticker) or suggest_type(ticker)
        if asset_type is None:
            unresolved.append(ticker)
        elif asset_type not in ASSET_TYPES:
            raise ValueError(f"{ticker}: '{asset_type}' is not a valid asset type")
        else:
            types[ticker] = asset_type
    return types, unresolved


# ---------------------------------------------------------------- database


def existing_tickers(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT ticker FROM assets")}


def existing_keys(conn) -> set[tuple[str, int]]:
    return {(r[0], r[1]) for r in conn.execute("SELECT fingerprint, occurrence FROM transactions")}


def import_trades(conn, rows: list[TradeRow], filename: str, types: dict[str, str]) -> tuple[int, int]:
    """Write the rows in ONE transaction. Returns (added, skipped). Caller commits."""
    asset_ids = {ticker: asset_id for ticker, asset_id in conn.execute("SELECT ticker, id FROM assets")}
    for ticker in sorted({r.ticker for r in rows} - asset_ids.keys()):
        if ticker not in types:
            raise ValueError(f"No type for new asset {ticker}")
        asset_ids[ticker] = conn.execute(
            "INSERT INTO assets (ticker, type) VALUES (%s, %s) RETURNING id", (ticker, types[ticker])
        ).fetchone()[0]

    batch_id = conn.execute(
        "INSERT INTO import_batches (source, filename, rows_added, rows_skipped) "
        "VALUES ('trades', %s, 0, 0) RETURNING id",
        (filename,),
    ).fetchone()[0]

    added = 0
    for r in rows:
        cursor = conn.execute(
            """
            INSERT INTO transactions
              (asset_id, trade_date, kind, quantity, total_value, institution, raw_ticker,
               fingerprint, occurrence, import_batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fingerprint, occurrence) DO NOTHING
            """,
            (asset_ids[r.ticker], r.trade_date, r.kind, r.quantity, r.total_value,
             r.institution, r.raw_ticker, r.fingerprint, r.occurrence, batch_id),
        )
        added += cursor.rowcount

    skipped = len(rows) - added
    conn.execute(
        "UPDATE import_batches SET rows_added = %s, rows_skipped = %s WHERE id = %s",
        (added, skipped, batch_id),
    )
    return added, skipped


# ---------------------------------------------------------------- command line


def print_report(conn, rows: list[TradeRow], warnings: list[str], chosen: dict[str, str]) -> list[str]:
    """Print the import report. Returns the tickers that still need a type."""
    keys = existing_keys(conn)
    new_rows = [r for r in rows if (r.fingerprint, r.occurrence) not in keys]
    tickers = sorted({r.ticker for r in rows})
    new_tickers = [t for t in tickers if t not in existing_tickers(conn)]
    _, unresolved = resolve_types(new_tickers, chosen)
    buys = [r for r in rows if r.kind == "buy"]
    sells = [r for r in rows if r.kind == "sell"]

    print(f"Rows read:        {len(rows)}  ({len(buys)} buys, {len(sells)} sells)")
    print(f"Date range:       {min(r.trade_date for r in rows)} -> {max(r.trade_date for r in rows)}")
    print(f"Total bought:     {sum(r.total_value for r in buys):,.2f}")
    print(f"Total sold:       {sum(r.total_value for r in sells):,.2f}")
    print(f"Fractional 'F':   {sum(1 for r in rows if r.ticker != r.raw_ticker)} rows normalized")
    print(f"New rows:         {len(new_rows)}   (already in database: {len(rows) - len(new_rows)})")
    print(f"Assets:           {len(tickers)} in file, {len(new_tickers)} new")
    if unresolved:
        print(f"Need a type:      {', '.join(unresolved)}  (pass --types)")
    print(f"Warnings ({len(warnings)}):")
    for warning in warnings:
        print("  -", warning)
    return unresolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a B3 'Negociação' export")
    parser.add_argument("file")
    parser.add_argument("--commit", action="store_true", help="write to the database")
    parser.add_argument("--types", help="JSON file {TICKER: type} for new assets")
    args = parser.parse_args()

    chosen = {}
    if args.types:
        with open(args.types) as f:
            chosen = json.load(f)

    rows, warnings = parse_trades_file(args.file)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        unresolved = print_report(conn, rows, warnings, chosen)
        if not args.commit:
            print("\nDry run: nothing written. Add --commit to import.")
            return
        if unresolved:
            raise SystemExit("\nAborted: some new assets have no type. Nothing written.")

        new_tickers = [t for t in {r.ticker for r in rows} if t not in existing_tickers(conn)]
        types, _ = resolve_types(new_tickers, chosen)
        added, skipped = import_trades(conn, rows, os.path.basename(args.file), types)
        print(f"\nImported: {added} added, {skipped} skipped (already existed).")


if __name__ == "__main__":
    main()
