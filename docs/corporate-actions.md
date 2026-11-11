# Corporate actions (design, not implemented yet)

## Problem
Events like stock splits, reverse splits, bonus shares and fraction auctions change
quantity (and sometimes cost) without a buy or sell. In the old system they were handled
by editing the spreadsheet by hand, which rewrites history and breaks verifiability.
`Bonificacao` rows were simply ignored by the calculation (TASA4F is missing 2 shares).

## Principle
**Never edit past transactions.** Each event is its own row in `corporate_actions`. The
position function walks transactions and events together, in date order. History stays
auditable, and the result can be explained event by event.

## Event kinds and their effect on the position

| Kind | Quantity | Total cost | Average price |
|---|---|---|---|
| Split (e.g. 1 → 2) | × ratio | unchanged | ÷ ratio |
| Reverse split (e.g. 100 → 1) | ÷ ratio (whole shares only) | unchanged | × ratio |
| Bonus shares | + bonus shares | + bonus shares × cost per share declared by the company | recomputed |
| Fraction auction (after a reverse split) | − leftover fraction | − proportional cost | unchanged |

Notes:
- A reverse split can leave a fraction (e.g. 50 shares at 100:1 = 0.5). The company sells
  fractions and credits cash. The position's fraction is removed and the cash is recorded
  as a sale of that fraction, so cost basis and cash stay consistent.
- A very large reverse split (the Americanas-type case) can reduce a small position to
  zero whole shares: the position disappears and only the fraction cash remains.
- Bonus shares add cost at the value per share declared by the company, not zero.
- Payouts received before the event keep their original amounts; only quantity-based
  comparisons need the adjusted quantity.

## Table (draft)
`corporate_actions(id, asset_id, date, kind, ratio_from, ratio_to, quantity, cost_per_share,
cash_amount, note)`. Only the fields relevant to the kind are filled.

## How events get in
1. **Manual form** (first version): pick asset, date, kind, ratio or amounts. One entry
   per event, ever.
2. **Detect and suggest**: when computed quantity differs from the B3 position or the
   movement report, flag "possible corporate action for ASSET around DATE" with a
   suggested ratio, and let the user confirm.
3. **B3 movement report**: check whether the Área do Investidor movement export lists
   these events (desdobro, grupamento, bonificação, fração). If it does, the importer
   can read them directly. To be confirmed with a real file.

## Verification
- Unit tests for each kind with hand-computed positions (split, reverse split with and
  without fraction, bonus, position going to zero).
- The position screen shows the event timeline per asset, so the user can see why the
  quantity and average price are what they are.

## Real cases found in the user's data (read-only analysis)

**AMER3F (Americanas)**: bought 54 shares on 2023-03-20 (R$ 60.48). The position was
removed by hand with a fake `Venda` of 54 shares at price 0.00 on 2024-08-27 (an older
version of the file had a sale of 54 at R$ 0.07 dated 2023-03-20). Effects: the
event is invisible, and the system books a total loss as if it were a trade. In the new
system this becomes a reverse split event plus a fraction (cash, possibly zero). The exact
ratio, date and any fraction cash must be confirmed from an official source (company
notice or B3 movement report); do not assume them.

**TASA4 (Taurus)**: 28 shares after the 2024 purchases, a `Bonificacao` of 2 shares on
2025-05-09, then sales of 28 + 2 on 2026-09-14 (30 total, consistent with the bonus
being real). The bonus row has `Valor` 7.89 = unit price while quantity is 2, so the
declared cost per share must be confirmed from the company notice.

**CPTS11 and BBAS3F (hand-edited splits)**: the old spreadsheet has quantities multiplied
by hand to absorb a split (CPTS11 ×10, BBAS3F ×2), with the original cost kept in `Valor`
(see `legacy-system-rules.md`). Plan: do **not** import those edited rows. Import the raw
B3 export (original quantities) and register the splits as events, so the result is the
same position but the history is untouched. The split dates and ratios must be confirmed
from official sources; they are not assumed here. CPTS11 is no longer held and BBAS3F is
(36 shares), so only BBAS3F affects the current portfolio.

### Confirmed with the raw B3 files (`backend/temp-data/`, git-ignored)

- Raw trades (2022-12-08 → 2026-09-23, 125 rows) have quantity **1** for the three
  CPTS11 buys and for the first BBAS3F buy, with `Valor` = `Preço`. This confirms the
  old spreadsheet's quantities were edited by hand. CPTS11: 3 shares bought, 30 sold →
  a 10:1 split happened. BBAS3F: 1 share bought at R$ 38.87 → ratio to be confirmed.
- The raw trades file has only `Compra` and `Venda`: **no corporate events at all**. The
  TASA4F `Bonificacao` row was also added by hand. The raw file shows 28 TASA4F bought
  and 30 sold, so the 2 extra shares really came from the bonus.
- AMER3F: the raw file has the 54-share purchase and **no sale**. The R$ 0 sale was
  invented in the old spreadsheet. Per the user, there was a **100:1 reverse split**
  (the user remembered 55 shares; the raw file says 54, to be checked). 54 / 100 = 0.54,
  so zero whole shares remain and only a fraction was left, which the company auctions for
  cash. Event date and fraction cash (if any) still need the B3 movement report or the
  company notice. Test case: reverse split 100:1 on 54 shares → position 0 + fraction cash.
- Conclusion: corporate events cannot be inferred from the trades export. They need
  the B3 movement report, official notices, or manual entry.

### Confirmed events from the B3 movement report

| Asset | Event | Date | Detail |
|---|---|---|---|
| CPTS11 | Desdobro | 2023-09-27 | +27 shares on 3 held → 10:1 |
| BBAS3 | Desdobro | 2024-04-17 | +1 on 1 held → 2:1 |
| AMER3 | Grupamento | 2024-08-28 | 54 → 0.54 (100:1) |
| AMER3 | Fração em Ativos | 2024-08-29 | −0.54 |
| AMER3 | Leilão de Fração | 2024-09-13 | 0.54 × R$ 6.636 = R$ 3.58 cash |
| TASA4 | Bonificação | 2025-05-09 | +2.80 (2 whole + 0.80 fraction) |
| TASA4 | Fração / Leilão | 2025-06-12 / 2025-07-08 | −0.80, R$ 5.40 cash |

So AMER3 is fully explained: 100:1, position becomes zero, R$ 3.58 cash. The user's
"55 shares" was 54. The TASA4 bonus is also explained (2 whole shares kept, 0.80 sold).
Other bonuses in the data: GGBR4 (2023-03-23, 2024-04-19), ALUP11 (2024-04-23,
2025-04-22), KLBN11/KLBN4 (2024-05-08, 2025-12-19), each with its fraction and auction.

**Bonus cost is not in the report** (`Preço unitário` and `Valor da Operação` are `-`).
It must come from the company notice (stored in `source_url`) or be entered manually.

**`Atualização` rows are B3 position snapshots.** BBAS3: 16 (2025-05-29), 36, 36, 58
(2026-09-02), which equals 2 (after the split) + 14 + 20 + 22 bought. This is a
second cross-check of the position logic, next to the payout `Quantidade`.

**Unit unbundling (KLBN11 → KLBN3 + KLBN4, `Transferência`, 2024-05-09)** moves quantity
between tickers. The model needs an "asset conversion" event; to design when KLBN is
implemented (cost basis must be split between the two new tickers).

## Cross-check: payout quantities

`Dividendos Recebidos.xlsx` has a `Quantidade` column: how many shares B3 says were held
at each payout. The position computed by the system at that date should match it. This
checks the whole position logic (purchases, sales, splits, bonus) against B3's own data,
and flags exactly where a corporate action is missing.

Example already visible: TASA4 payouts in 2025-05-20, 2025-07-22 and 2025-09-23 list 28
shares, but the position after the bonus would be 30. Either the bonus shares were
credited later or the bonus date/quantity needs checking.

## Out of scope for now
- Ticker changes and mergers (an asset becoming another). Likely an asset alias/successor
  link, to be designed when the first real case appears.
