"""Read the B3 'Movimentação' export (corporate events, fixed income, position snapshots).

Parses, classifies and reports. With --commit it also writes:
- corporate events (split, reverse split, bonus, fraction + auction cash, transfers between
  tickers) to `corporate_actions`;
- fixed income (CDB, LCA, Tesouro): purchases and redemptions as `transactions`, CDB/LCA
  interest as `payouts`, and an empty `fixed_income_terms` row per product (index and rate
  come from the user). Tesouro coupons come from the Proventos file, not from here.
Snapshots (`Atualização`) are not written.

    docker compose exec api python -W ignore -m app.importers.movements "temp-data/<file>.xlsx"
    docker compose exec api python -W ignore -m app.importers.movements "temp-data/<file>.xlsx" --commit

Re-importing the same or an overlapping file is safe: rows are recognized by
(fingerprint, occurrence).

See docs/import.md (Movimentação table) and docs/corporate-actions.md for the meaning of
each movement type.
"""
import argparse
import hashlib
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg
from openpyxl import load_workbook

from app.importers.payouts import PayoutRow, import_payouts
from app.importers.trades import TradeRow, _canonical, _to_date, _to_decimal, import_trades, suggest_type

REQUIRED_COLUMNS = [
    "Entrada/Saída",
    "Data",
    "Movimentação",
    "Produto",
    "Instituição",
    "Quantidade",
    "Preço unitário",
    "Valor da Operação",
]

# Movement type -> what the importer does with it.
CORPORATE = {
    "Desdobro": "split",
    "Grupamento": "reverse_split",
    "Bonificação em Ativos": "bonus",
    "Fração em Ativos": "fraction",
    "Leilão de Fração": "fraction_auction",
    "Transferência": "conversion",  # e.g. KLBN11 -> KLBN3 + KLBN4, needs its own design
}
SNAPSHOT = "Atualização"
FIXED_INCOME = {
    "COMPRA / VENDA",
    "VENCIMENTO/RESGATE SALDO EM CONTA",
    "PAGAMENTO DE JUROS",
    "Compra",  # Tesouro Direto
}
# Known and deliberately not used for positions (see docs/import.md).
IGNORED = {
    "Direito de Subscrição",
    "Direitos de Subscrição - Não Exercido",
    "Cessão de Direitos",
    "Cessão de Direitos - Solicitada",
    "Transferência - Liquidação",  # settlement of trades: use the Negociação file instead
    "Rendimento",
    "Dividendo",
    "Juros Sobre Capital Próprio",
    "Juros",  # payouts: come from the Proventos file
}
# Temporary tickers of the Americanas reverse split, ignored on the user's instruction.
IGNORED_TICKERS = {"AMER1", "AMER95"}
SIMPLE_KINDS = {"Desdobro": "split", "Grupamento": "reverse_split",
                "Bonificação em Ativos": "bonus", "Fração em Ativos": "fraction"}
TRANSFER_KINDS = {"Debito": "transfer_out", "Credito": "transfer_in"}  # for 'Transferência'
TICKER = re.compile(r"[A-Z]{4}\d{1,2}")


@dataclass(frozen=True)
class MovementRow:
    line: int
    event_date: date
    direction: str  # 'Credito' | 'Debito'
    movement: str
    product: str  # as in the file
    ticker: str | None  # None for fixed income products
    institution: str
    quantity: Decimal | None
    unit_price: Decimal | None
    value: Decimal | None


def _optional_decimal(value) -> Decimal | None:
    if value is None or str(value).strip() in ("", "-"):
        return None
    return _to_decimal(value)


def _ticker_of(product: str) -> str | None:
    """'GGBR4 - GERDAU S/A' -> 'GGBR4'. Fixed income ('CDB - ...') has no ticker."""
    head = product.split(" - ")[0].strip()
    return head if TICKER.fullmatch(head) else None


def parse_movements_file(path: str) -> tuple[list[MovementRow], list[str]]:
    """Return (rows, warnings). Raises ValueError if the file is not a Movimentação export."""
    sheet = load_workbook(path, data_only=True).active  # not read_only, see trades.py
    lines = sheet.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(lines)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"Not a B3 movement export, missing columns: {missing}")
    col = {name: header.index(name) for name in REQUIRED_COLUMNS}

    rows, warnings = [], []
    for line_number, line in enumerate(lines, start=2):
        if all(cell is None for cell in line):
            continue
        product = str(line[col["Produto"]]).strip()
        rows.append(
            MovementRow(
                line=line_number,
                event_date=_to_date(line[col["Data"]]),
                direction=str(line[col["Entrada/Saída"]]).strip(),
                movement=str(line[col["Movimentação"]]).strip(),
                product=product,
                ticker=_ticker_of(product),
                institution=str(line[col["Instituição"]]).strip(),
                quantity=_optional_decimal(line[col["Quantidade"]]),
                unit_price=_optional_decimal(line[col["Preço unitário"]]),
                value=_optional_decimal(line[col["Valor da Operação"]]),
            )
        )
    return rows, warnings


def classify(row: MovementRow) -> str:
    """'corporate' | 'snapshot' | 'fixed_income' | 'ignored' | 'unknown'."""
    if row.ticker in IGNORED_TICKERS:
        return "ignored"
    if row.movement in CORPORATE:
        return "corporate"
    if row.movement == SNAPSHOT:
        return "snapshot"
    if row.movement in FIXED_INCOME and row.ticker is None:
        return "fixed_income"
    if row.movement in IGNORED:
        return "ignored"
    return "unknown"


def check_fraction_trios(rows: list[MovementRow]) -> list[str]:
    """Every fraction debit should have an auction credit of the same quantity, and vice versa."""
    debits = defaultdict(list)
    credits = defaultdict(list)
    for r in rows:
        if r.movement == "Fração em Ativos":
            debits[r.ticker].append(r.quantity)
        elif r.movement == "Leilão de Fração":
            credits[r.ticker].append(r.quantity)
    problems = []
    for ticker in sorted(set(debits) | set(credits)):
        left, right = sorted(debits[ticker]), sorted(credits[ticker])
        if left != right:
            problems.append(f"{ticker}: fraction debits {left} vs auction credits {right}")
    return problems


# ---------------------------------------------------------------- corporate actions


@dataclass(frozen=True)
class ActionRow:
    ticker: str
    action_date: date
    kind: str  # split | reverse_split | bonus | fraction
    quantity: Decimal  # as B3 reports it: extra shares (split), resulting shares (reverse split)
    cash_amount: Decimal | None  # fractions only: cash of the auction
    note: str
    fingerprint: str
    occurrence: int


def plan_corporate_actions(
    rows: list[MovementRow], known: set[str]
) -> tuple[list[ActionRow], dict[str, str], list[str]]:
    """Turn corporate rows into ActionRows.

    Returns (actions, new_assets {ticker: type}, notes about what was skipped).
    A ticker not in the database yet is created when its type is unambiguous (4 letters +
    digit, e.g. KLBN3); otherwise its events are skipped and reported.
    """
    notes = []
    new_assets: dict[str, str] = {}

    # Pair each fraction debit with its auction (same asset and quantity, in date order).
    auctions = defaultdict(list)
    for r in sorted(rows, key=lambda r: r.event_date):
        if r.movement == "Leilão de Fração":
            auctions[(r.ticker, r.quantity)].append(r)

    seen: Counter = Counter()
    actions = []
    for r in sorted(rows, key=lambda r: (r.event_date, r.ticker or "", r.movement, r.direction)):
        if classify(r) != "corporate" or r.movement == "Leilão de Fração":
            continue
        if r.ticker not in known and r.ticker not in new_assets:
            asset_type = suggest_type(r.ticker)
            if asset_type is None:
                notes.append(f"{r.event_date} {r.ticker}: {r.movement} skipped, asset not in the database and type unclear")
                continue
            new_assets[r.ticker] = asset_type

        key_parts = [r.event_date.isoformat(), r.ticker, r.movement, _canonical(r.quantity), r.institution]
        cash, note = None, ""
        if r.movement == "Transferência":
            kind = TRANSFER_KINDS[r.direction]
            note = "cost carried unknown (see company notice)"
            key_parts.append(r.direction)  # the debit and the credit of a ticker must differ
        else:
            kind = SIMPLE_KINDS[r.movement]
            if kind == "fraction":
                pending = auctions[(r.ticker, r.quantity)]
                if pending:
                    auction = pending.pop(0)
                    cash = auction.value
                    note = f"auction on {auction.event_date} at {auction.unit_price}"
            elif kind == "bonus":
                note = "cost per share unknown (see company notice)"
        fingerprint = hashlib.sha256("|".join(key_parts).encode()).hexdigest()
        seen[fingerprint] += 1
        actions.append(ActionRow(r.ticker, r.event_date, kind, r.quantity, cash, note, fingerprint, seen[fingerprint]))
    return actions, new_assets, notes


def import_actions(
    conn, actions: list[ActionRow], new_assets: dict[str, str], filename: str
) -> tuple[int, int, int]:
    """Write in ONE transaction. Returns (added, updated, skipped). Caller commits.

    'updated' = an existing fraction that only now got its auction cash.
    """
    asset_ids = {t: i for t, i in conn.execute("SELECT ticker, id FROM assets")}
    for ticker, asset_type in new_assets.items():
        if ticker not in asset_ids:
            asset_ids[ticker] = conn.execute(
                "INSERT INTO assets (ticker, type) VALUES (%s, %s) RETURNING id", (ticker, asset_type)
            ).fetchone()[0]
    batch_id = conn.execute(
        "INSERT INTO import_batches (source, filename, rows_added, rows_skipped) "
        "VALUES ('movements', %s, 0, 0) RETURNING id",
        (filename,),
    ).fetchone()[0]
    added = updated = 0
    for a in actions:
        row = conn.execute(
            """
            INSERT INTO corporate_actions
              (asset_id, action_date, kind, quantity, cash_amount, note, fingerprint, occurrence, import_batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fingerprint, occurrence) DO UPDATE
              SET cash_amount = EXCLUDED.cash_amount, note = EXCLUDED.note
              WHERE corporate_actions.cash_amount IS NULL AND EXCLUDED.cash_amount IS NOT NULL
            RETURNING (xmax = 0)
            """,
            (asset_ids[a.ticker], a.action_date, a.kind, a.quantity, a.cash_amount, a.note,
             a.fingerprint, a.occurrence, batch_id),
        ).fetchone()
        if row is not None:
            added += row[0]
            updated += not row[0]
    skipped = len(actions) - added - updated
    conn.execute(
        "UPDATE import_batches SET rows_added = %s, rows_skipped = %s WHERE id = %s",
        (added, skipped, batch_id),
    )
    return added, updated, skipped


def write_asset_names(conn, rows: list[MovementRow]) -> int:
    """Fill assets.name from 'TICKER - COMPANY NAME' (only where it is still empty)."""
    names = {}
    for r in rows:
        if r.ticker and " - " in r.product:
            names[r.ticker] = r.product.split(" - ", 1)[1].strip()
    updated = 0
    for ticker, name in names.items():
        updated += conn.execute(
            "UPDATE assets SET name = %s WHERE ticker = %s AND name IS NULL", (name, ticker)
        ).rowcount
    return updated


# ---------------------------------------------------------------- fixed income


@dataclass(frozen=True)
class FixedIncomePlan:
    assets: dict  # ticker -> (type, name, issuer, maturity_date or None)
    trades: list  # TradeRow
    payouts: list  # PayoutRow
    notes: list


def parse_fixed_income_product(product: str) -> tuple[str, str, str | None, str]:
    """'CDB - CDB223RB92P - BANCO BMG S/A' -> (ticker, type, issuer, name).

    The code is the ticker; Tesouro has no code, so its name is the ticker (same as in the
    Proventos file).
    """
    parts = [p.strip() for p in product.split(" - ")]
    if parts[0] in ("CDB", "LCA", "LCI", "LC", "CRI", "CRA", "DEBENTURE") and len(parts) >= 2:
        return parts[1], "fixed_income", (parts[2] if len(parts) > 2 else None), product
    if product.startswith("Tesouro"):
        return product, "treasury", None, product
    return product, "fixed_income", None, product


def plan_fixed_income(rows: list[MovementRow]) -> FixedIncomePlan:
    assets, trades, payouts, notes = {}, [], [], []
    seen: Counter = Counter()
    for r in sorted((r for r in rows if classify(r) == "fixed_income"), key=lambda r: (r.event_date, r.product)):
        ticker, asset_type, issuer, name = parse_fixed_income_product(r.product)
        if r.quantity is None or r.value is None:
            notes.append(f"{r.event_date} {ticker}: {r.movement} without quantity or value, skipped")
            continue
        maturity = assets.get(ticker, (None, None, None, None))[3]

        if r.movement == "PAGAMENTO DE JUROS":
            fingerprint = hashlib.sha256(
                "|".join([r.event_date.isoformat(), ticker, r.movement, _canonical(r.quantity),
                          _canonical(r.value), r.institution]).encode()
            ).hexdigest()
            seen[fingerprint] += 1
            payouts.append(PayoutRow(r.event_date, ticker, "interest", r.movement, r.quantity, r.value,
                                     r.institution, fingerprint, seen[fingerprint]))
        else:
            if r.movement in ("COMPRA / VENDA", "Compra"):
                kind = "buy" if r.direction == "Credito" else "sell"
            elif r.movement == "VENCIMENTO/RESGATE SALDO EM CONTA":
                kind = "sell"
                maturity = r.event_date
            else:
                notes.append(f"{r.event_date} {ticker}: unhandled {r.movement}, skipped")
                continue
            fingerprint = hashlib.sha256(
                "|".join([r.event_date.isoformat(), r.product, kind, _canonical(r.quantity),
                          _canonical(r.value), r.institution]).encode()
            ).hexdigest()
            seen[fingerprint] += 1
            trades.append(TradeRow(r.event_date, kind, ticker, r.product, r.quantity, r.value,
                                   r.institution, fingerprint, seen[fingerprint]))
        assets[ticker] = (asset_type, name, issuer, maturity)
    return FixedIncomePlan(assets, trades, payouts, notes)


def import_fixed_income(conn, plan: FixedIncomePlan, filename: str) -> dict:
    """Write in ONE transaction. Returns counts. Caller commits."""
    types = {ticker: info[0] for ticker, info in plan.assets.items()}
    added_trades, skipped_trades = import_trades(conn, plan.trades, filename, types, source="movements")
    added_payouts, skipped_payouts = import_payouts(conn, plan.payouts, filename, types, source="movements")
    for ticker, (_, name, issuer, maturity) in plan.assets.items():
        asset_id = conn.execute("UPDATE assets SET name = COALESCE(name, %s) WHERE ticker = %s RETURNING id",
                                (name, ticker)).fetchone()[0]
        conn.execute(
            """
            INSERT INTO fixed_income_terms (asset_id, issuer, maturity_date) VALUES (%s, %s, %s)
            ON CONFLICT (asset_id) DO UPDATE SET
              issuer = COALESCE(fixed_income_terms.issuer, EXCLUDED.issuer),
              maturity_date = COALESCE(fixed_income_terms.maturity_date, EXCLUDED.maturity_date)
            """,
            (asset_id, issuer, maturity),
        )
    return {"trades": (added_trades, skipped_trades), "payouts": (added_payouts, skipped_payouts)}


# ---------------------------------------------------------------- command line


def print_report(rows: list[MovementRow], warnings: list[str]) -> None:
    kinds = {r.line: classify(r) for r in rows}
    by_movement = Counter((kinds[r.line], r.movement) for r in rows)

    print(f"Rows read:   {len(rows)}")
    print(f"Date range:  {min(r.event_date for r in rows)} -> {max(r.event_date for r in rows)}")
    print("\nWhat each movement type will be used for:")
    for (kind, movement), count in sorted(by_movement.items()):
        print(f"  {kind:13} {movement:42} {count:4}")

    unknown = [r for r in rows if kinds[r.line] == "unknown"]
    print(f"\nUnknown movement types ({len(unknown)}):")
    for r in unknown[:20]:
        print(f"  line {r.line}: {r.movement!r} on {r.product}")

    print("\nCorporate events (the ones that change positions):")
    print(f"  {'date':10}  {'ticker':8} {'event':22} {'qty':>10} {'unit':>9} {'cash':>8}")
    for r in sorted((r for r in rows if kinds[r.line] == "corporate"), key=lambda r: (r.event_date, r.ticker or "")):
        unit = f"{r.unit_price:.4f}" if r.unit_price is not None else "-"
        cash = f"{r.value:.2f}" if r.value is not None else "-"
        print(f"  {r.event_date}  {r.ticker or '?':8} {r.movement:22} {r.quantity or 0:10.4f} {unit:>9} {cash:>8}")

    problems = check_fraction_trios(rows)
    print(f"\nFraction check (debit = auction credit, per asset): {'OK' if not problems else ''}")
    for p in problems:
        print("  !", p)

    fixed = {r.product for r in rows if kinds[r.line] == "fixed_income"}
    print(f"\nFixed income products ({len(fixed)}), for the fixed income module:")
    for product in sorted(fixed):
        print("  -", product)
    snapshots = sum(1 for r in rows if kinds[r.line] == "snapshot")
    print(f"\nPosition snapshots (Atualização): {snapshots}, kept for the cross-check")
    print(f"Warnings ({len(warnings)}):")
    for w in warnings:
        print("  -", w)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report on a B3 'Movimentação' export")
    parser.add_argument("file")
    parser.add_argument("--commit", action="store_true", help="write corporate events to the database")
    args = parser.parse_args()
    rows, warnings = parse_movements_file(args.file)
    print_report(rows, warnings)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        known = {r[0] for r in conn.execute("SELECT ticker FROM assets")}
        actions, new_assets, notes = plan_corporate_actions(rows, known)
        existing = {(r[0], r[1]) for r in conn.execute("SELECT fingerprint, occurrence FROM corporate_actions")}
        new = [a for a in actions if (a.fingerprint, a.occurrence) not in existing]
        print(f"\nTo write to corporate_actions: {len(actions)} events ({len(new)} new, {len(actions) - len(new)} already there)")
        if new_assets:
            print("  new assets to create:", ", ".join(f"{t} ({k})" for t, k in new_assets.items()))
        for note in notes:
            print("  skipped:", note)
        plan = plan_fixed_income(rows)
        print(f"\nFixed income: {len(plan.assets)} products, {len(plan.trades)} buys/redemptions, "
              f"{len(plan.payouts)} interest payments")
        for t in plan.trades:
            print(f"  {t.trade_date} {t.kind:4} {t.ticker[:28]:28} qty {t.quantity:>10} value {t.total_value:>9}")
        for p in plan.payouts:
            print(f"  {p.pay_date} interest {p.ticker[:28]:28} qty {p.quantity_held:>10} value {p.net_amount:>9}")
        for note in plan.notes:
            print("  skipped:", note)
        if not args.commit:
            print("\nDry run: nothing written. Add --commit to import.")
            return
        filename = os.path.basename(args.file)
        write_asset_names(conn, rows)
        added, updated, skipped = import_actions(conn, actions, new_assets, filename)
        print(f"\nCorporate events: {added} added, {updated} updated with auction cash, {skipped} skipped.")
        counts = import_fixed_income(conn, plan, filename)
        print(f"Fixed income trades: {counts['trades'][0]} added, {counts['trades'][1]} skipped; "
              f"interest: {counts['payouts'][0]} added, {counts['payouts'][1]} skipped.")


if __name__ == "__main__":
    main()
