# Legacy system rules and problems

Survey of `../SpreadsheetInvestmentReader` (`Wallet.py`, `Dividends.py`). Basis for the
database schema and for verifying the migration.

## Spreadsheet format

**Negociações.xlsx** (columns used): `Data do Negócio`, `Tipo de Movimentação`
(`Compra`/`Venda`/`Bonificacao`), `Código de Negociação`, `Quantidade`, `Valor` (**total
of the operation**, not unit price), `Ano`, `Mês`.

**Dividendos Recebidos.xlsx**: `Produto` (`TICKER - Name`), `Pagamento`,
`Tipo de Evento`, `Valor líquido`, `Ano`, `Mês`.

- `Ano` and `Mês` are required by the old code and **do not come from B3**: they are
  columns added by hand. In the new system they are derived from the date.
- The other columns are exactly the B3 exports (trades and payouts).
- Tesouro Direto appears in `Código de Negociação` by **name** (contains "Tesouro").

## Business rules

1. **Position per asset**: purchases become lots `(quantity, value)`. Sales consume the
   oldest lots (FIFO), reducing the lot value proportionally. Average price = remaining
   value / remaining quantity. Assets with quantity 0 disappear.
2. **Total invested** = sum of the value of open positions.
3. **Type classification** (heuristic on the code text):
   - first 4 letters in the FII list → `FII`
   - code in the stock list → stock
   - code in the Fiagro list → `FIAGRO`
   - name containing "Tesouro" → `Tesouro Direto`
   - the `F` suffix (fractional market, e.g. `PETR4F`) is stripped before comparing.
4. **Distribution** = value per type / total (stock, fii, fiagro, tesouro).
5. **Monthly contribution** = sum of purchases per month, last 12 months.
6. **Payouts**: category from the `Tipo de Evento` text → `Dividendo/Rendimento`
   (contains "dividendo" or "rendimento"), `JCP`, `Juros`, `Outro`. The net value is used.
7. **Monthly yield (%)** = payouts of the month / total invested up to that month,
   **excluding Tesouro**.

## Problems found (do not replicate)

| # | Problem | Effect |
|---|---|---|
| 1 | FIFO logic copied in `calculateAmount` and `generateCompleteReport` | Future divergence |
| 2 | `calculateAmountAppliedUpToDate*` computes `buys − sells` (uses the sale value, not cost) | "Total invested" differs from FIFO depending on the endpoint |
| 3 | In the no-Tesouro version, the exclusion only applies to the current year (`\|`/`&` precedence) and only filters "Tesouro IPCA" | Wrong yield % |
| 4 | Those functions overwrite `self.investment_df` and `self.total` | Corrupted state; `server.py` reuses a global `myWallet` across requests |
| 5 | `FIIs`, `Stock`, `Fiagro` use a class-level list and `append` on every instance | Lists grow on each request |
| 6 | `getDividendFromYearAndMonth` defined twice; `getDividendsByYear` filters by text (`str.contains(year)`); `getDividendsByYearAndType` returns nothing | Dead and fragile code |
| 7 | Values stored as `float` | Rounding errors; use `NUMERIC` in Postgres |
| 8 | Stock split, reverse split and bonus issues not handled (`Bonificacao` is ignored) | Wrong quantity and average price |

## Consequences for the new system

- `transactions` stores `total_value` (not unit price).
- The asset type lives in the `assets` table, filled once, with no text heuristics.
- A single position function used by all reports, with no shared state.
- Cost basis method decided: weighted average price.
- `quantity` needs decimals (Tesouro: 0.11 bond). Use `NUMERIC`.
- Treat `Bonificacao` as a quantity entry with cost.

## Data anomalies found (to be verified by the user)

Read-only analysis of `Negociações.xlsx` (122 rows) and `Dividendos Recebidos.xlsx`
(652 rows). None were fixed; the user checks them against brokerage notes.

| Where | What | Suspicion |
|---|---|---|
| Trades, 4 rows (CPTS11 ×3 and BBAS3F, 2023) | `Valor` equals the unit price, but `Quantidade` > 1 | **Most likely manual split adjustments, not errors**: the user multiplied the quantity by hand (CPTS11 ×10, BBAS3F ×2) and left the real cost in `Valor`. Evidence: CPTS11 sold 30 shares at R$ 8.46 (post-split price) after buying 3 × "10" at ~R$ 76–88; BBAS3F later buys are at ~R$ 22–26. So `Valor` is probably right and `Quantidade`/`Preço` are the edited fields. The raw B3 export would show the original quantities. |
| Trades, Tesouro IPCA+ 2055 (2024-09-03) | `Preço` 60,103.82 inconsistent with `Valor` 472.24 for 0.11 bond | `Valor` looks correct; `Preço` is suspect |
| Trades, TASA4F `Bonificacao` (2025-05-09) | Ignored by the old calculation; `Valor` equals the unit price | 2 shares missing from the position |
| Payouts, WEGE3 JCP (2025-12-12) | Two identical rows | Possible paste duplication |

### Resolution after comparing with the raw B3 files

- CPTS11 / BBAS3F: confirmed hand-edited splits (Desdobro 10:1 on 2023-09-27 and 2:1 on
  2024-04-17). The raw `Valor` was right.
- Tesouro IPCA+ 2055: the trades export does not contain it at all. The Movimentação shows
  0.11 bond at R$ 4,293.13 = R$ 472.24, so `Valor` was right and `Preço` 60,103.82 was a
  hand-typed error.
- TASA4F bonus: confirmed (+2.80 on 2025-05-09, 0.80 sold for R$ 5.40). Only the cost per
  bonus share is still missing.
- WEGE3 JCP duplicate: the raw payout files also contain identical repeated lines
  (only 1 in the new import: WEGE3 2025-12-12); kept as they come from B3.

No other problems: no negative positions, no exact duplicate rows in trades, and
`Mês`/`Ano` consistent with the dates.
