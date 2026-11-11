# Positions (weighted average price)

Code: `backend/app/positions.py` (pure function `compute_position`), tests in
`backend/tests/test_positions.py`, report in `backend/app/positions_report.py`.
Nothing is stored: positions are computed from `transactions` every time.

## Rules
- Buy: quantity += q, cost += value.
- Sell: cost leaving = q x average price (not the sale value); the average price does not
  change; realized profit = sale value - cost leaving.
- Same day: buys count before sells (B3 trades have no time of day).
- A sale larger than the position produces a warning and never makes the quantity negative.
- Corporate actions take effect at the start of their date, before that day's trades, with
  B3's own numbers: split = extra shares credited (+27 on 3 held = 10:1), reverse split =
  resulting shares (54 -> 0.54), bonus = shares credited (cost per share unknown counts as
  0 and warns), fraction = leftover removed at average price with the auction cash as its
  sale value. Tests: 14.

## How to run
```
docker compose exec api python -m unittest discover -s tests -t . -v   # 14 tests
docker compose exec api python -W ignore -m app.positions_report        # table
docker compose exec api python -W ignore -m app.positions_report --csv  # for comparisons
```

## Comparison with the old system (FIFO over the old `Negociações.xlsx`)
Old sheet: 122 rows, 2022-12-08 → 2026-09-14. Raw B3 file: 125 rows → 2026-09-23.
Total cost: old 14,979.02 (includes 2 fixed income products and "Caixinha") vs new
12,708.61 (stocks, FII, Fiagro, ETF only). Every quantity difference is explained:

| Asset | Old → New | Reason |
|---|---|---|
| ALUP11, ITSA4, SAPR4, TGAR11, XPML11 | differ | Trades after 2026-09-14 exist only in the new file |
| BBAS3 | 36 → 57 | 22 shares bought 2026-06-17 are missing in the old sheet; the old +1 was a hand-multiplied split (new system waits for the split event) |
| AMER3 | 0 → 54 | Old sheet had a fake R$0 sale; the real event is a reverse split + fraction auction (Movimentação) |
| CDB BMG, Caixinha, LCA BTG | old only | Fixed income, comes with the fixed income module |
| CPTS11, TASA4 | both 0 | Match, but only by accident (hand edits in the old sheet) |
| All others | match | Same quantity and cost |

### After applying the corporate events (14 imported from Movimentação)
Before the events the calculation warned about CPTS11 (sold 30 with 3), TASA4 (sold 28
with 26) and GGBR4 (sold 16 with 14). With the events those warnings are gone, and:
- BBAS3 now 58 shares, equal to the B3 `Atualização` snapshot of 2026-09-02.
- AMER3 closes with a realized loss of -56.90 (cost 60.48, auction cash 3.58).
- Total invested (open positions): 12,632.44. Realized: -899.47.
- Remaining warnings: bonus with unknown cost (ALUP11 x2, GGBR4 x2, TASA4 x1). The cost
  per share must come from the company notices; until then they count as 0, which makes
  the average price of those assets a bit low.
- KLBN11 is still wrong (27 shares): the unit conversions are not modeled yet.

Cost differences between FIFO and weighted average only appear after partial sales; none
of the open positions above had a cost-only difference.

TGAR11 closed with a realized loss of -735.66 (12 bought for 1,266.08, sold for 530.42,
about 44 per share). Confirmed by the user as a real loss; no corporate event involved.
