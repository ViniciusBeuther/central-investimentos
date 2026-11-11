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

## Out of scope for now
- Ticker changes and mergers (an asset becoming another). Likely an asset alias/successor
  link, to be designed when the first real case appears.
