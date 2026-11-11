# Fixed income (CDB, LCA, Tesouro)

Imported from the Movimentação report by `backend/app/importers/movements.py` (same command
and `--commit` as the corporate events; re-running adds 0).

## Model
- Each product is an `assets` row: type `fixed_income` (CDB, LCA) or `treasury`. Ticker =
  the product code (`CDB223RB92P`, `25L02260280`); Tesouro uses its name. `name` keeps the
  full B3 product text.
- Purchase and redemption are ordinary `transactions` (`COMPRA / VENDA` credit and `Compra`
  = buy, `VENCIMENTO/RESGATE` = sell). Quantity is in units, value is the total.
- CDB/LCA interest (`PAGAMENTO DE JUROS`) is a `payouts` row of kind `interest`. Tesouro
  coupons (`Juros`) are NOT read here: they come from the Proventos file.
- `fixed_income_terms` (migration `0004`) holds the rule B3 does not report: `index_name`
  (cdi, selic, ipca, prefixed), `rate`, `maturity_date`, plus the issuer parsed from the
  product text. Rows are created empty; index and rate are pending from the user. The
  maturity is filled automatically when a redemption exists.

## Real data
| Product | Events | Result |
|---|---|---|
| CDB BMG (`CDB223RB92P`) | bought 2025-11-05 for 1,011.93; redeemed 2026-06-12: 903.44 + 202.42 interest | closed; real gain 93.93 |
| LCA BTG (`25L02260280`) | bought 2025-12-08 for 1,000.00 | open |
| CDB `CDB220EM2H3` (issuer not shown) | bought 2026-06-12, 604 units, 1,087.03 | open |
| Tesouro IPCA+ 2055 | bought 2024-09-03, 0.11 bond, 472.24; 4 coupons | open |

Total invested (open positions, all types): 15,191.71.

## Caveats
- B3 splits a redemption into "principal" and "interest" lines. The positions report books
  the principal line as a sale, so CDB BMG shows a realized loss of -108.49; the interest
  payout (+202.42) is separate. The true result is the sum (+93.93). The fixed income
  screen must show it that way.
- The old system had a "Caixinha" (920) that is not in any B3 file; if it still exists it
  lives outside B3 and must be entered manually.
- Current value is not computed yet: it needs index/rate and Central Bank series (SGS).
