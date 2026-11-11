# Importing B3 data (design, not implemented yet)

## Problem
Today: download the spreadsheet from B3, open the master spreadsheet, copy columns, paste,
fill `Mês`/`Ano` by hand. Once for trades and once for payouts. It is slow and error-prone
(see the anomalies in `legacy-system-rules.md`).

## Target flow (about 1 minute)
1. Download the files from B3's Área do Investidor (trades and payouts).
2. Drag the files onto the import screen.
3. Review the preview and confirm.

B3 login (gov.br) is not automated: the download stays manual.

## Importer rules
- **Reads the raw B3 file** without editing it. `Mês`/`Ano` are derived from the date.
- **Idempotent**: the full history can be uploaded every time; only new rows are added.
  - Row key: date, asset, type, quantity, value, institution, plus an occurrence counter
    among identical rows. Two genuinely identical rows are both imported, while
    re-importing the same file does not duplicate anything.
- **Preview before writing**: "12 new, 110 already existed, 2 with warnings".
- **Validations** (warn, do not block):
  - `Valor` ≠ quantity × price
  - unknown movement type (bonus, split, reverse split…)
  - new asset without a type (ask once and store it in `assets`)
  - sale larger than the position
  - sale with price 0 (usually a manual "zeroing" of a position, e.g. AMER3F; should be a
    corporate action instead)
  - computed position at a payout date ≠ `Quantidade` of that payout (see
    `corporate-actions.md`)
  - payout identical to another one (possible duplicate)
- **Check against B3**: if the position export is available, compare quantities per asset
  with the computed ones and flag divergences.

## Duplicate guard (three layers)

B3 exports have no unique row ID, so identity is built from the row content.

1. **Fingerprint + occurrence counter** (the import logic above). Fingerprint = date,
   asset, type, quantity, value, institution. The counter numbers identical rows within
   the file (1st, 2nd…). Re-importing the same or an overlapping file matches the
   existing rows and adds nothing; two genuinely identical rows both import.
2. **"Where did I stop" on the import screen**: before uploading, show the last imported
   date per source (trades, payouts) and per asset, and the history of imports (file
   name, time, rows added/skipped). After upload, show the file's date range next to the
   database's, and highlight only the new rows in the preview.
3. **Database constraint as the last line of defense**: a unique index on
   (source, fingerprint, occurrence), so even a bug in the app cannot insert the same
   row twice.

Extra behaviors:
- Every row stores an `import_batch_id`. A whole import can be undone in one action
  (with confirmation), which makes a wrong upload harmless.
- Manual entries (form) run the same check and warn: "a transaction with the same asset,
  date, quantity and value already exists".
- The guard warns instead of blocking when it finds an ambiguous case (e.g. the WEGE3 JCP
  pair, which may be legitimate), and the user decides.

## Routine: what to upload and in which cases

Three B3 files cover everything. The user drops them all at once; the system detects each
type by its columns and processes them in the right order (trades → movement → payouts),
so the upload order does not matter.

| File | How much to download | Why it is needed |
|---|---|---|
| Negociação | Whole history (idempotent) or since the last imported date | Buys and sells with the trade date |
| Movimentação | Whole history (idempotent) or since the last imported date | Splits, bonus, fractions, fixed income, position snapshots |
| Proventos recebidos | Current year (or since the last imported date) | Dividends, JCP, income |

Monthly routine (about 5 minutes), and also right after any trade or corporate event:
1. Download the three files from B3 (the import screen shows the last imported date).
2. Drop them on the import screen.
3. Review the import report: new rows, warnings.
4. Answer only what the system cannot know (below), then confirm.
5. Look at the **data quality panel**; green means the data can be trusted.

Only manual inputs left:
- type of a ticker seen for the first time (suggested, confirm once);
- index and rate of each new fixed income product (e.g. 110% CDI), once per product;
- cost per share of a bonus (optional, with a link to the company notice);
- crypto and USD (not in B3 files).

Data quality panel (each check uses data from a different file):
- computed position at each payout date = payout `Quantidade` (Proventos × Negociação +
  Movimentação events);
- computed position = `Atualização` snapshots (Movimentação);
- every `Fração em Ativos` has its `Leilão de Fração`, and every event has its asset;
- no sale larger than the position, no sale at price 0, no unknown movement type;
- no asset without a type, no fixed income without index/rate;
- duplicates: none inserted (reported with counts per import).

## B3 reports and what each one is for

| Report | Contains | Use |
|---|---|---|
| Negociação | Buys and sells with the **trade date** | `transactions` |
| Proventos recebidos | Dividends, JCP, income credited | `payouts` |
| Movimentação | Every custody movement (see below) | `corporate_actions`, fixed income, position snapshots, payout cross-check |

Movimentação does not replace Negociação: trades appear there by settlement date, not
trade date, which would shift cost and dates (117 settlement rows vs 125 trades).

### Movimentação: confirmed with a real file (1053 rows, 2022-12-12 → 2026-10-23)

Columns: `Entrada/Saída` (Credito/Debito), `Data`, `Movimentação`, `Produto`, `Instituição`,
`Quantidade`, `Preço unitário`, `Valor da Operação` (`-` when empty). `Produto` is
`TICKER - NAME`; fixed income is `CDB - <code> - <issuer>`.

| `Movimentação` value | Meaning | Handling |
|---|---|---|
| `Desdobro` | Split; `Quantidade` = **extra** shares credited | `corporate_actions` split |
| `Grupamento` | Reverse split; `Quantidade` = resulting (fractional) shares | `corporate_actions` reverse split |
| `Bonificação em Ativos` | Bonus shares, **fractional quantity** (e.g. 2.80), no cost | `corporate_actions` bonus; cost from company notice |
| `Fração em Ativos` (Debito) | Fraction removed from the position | `corporate_actions` fraction |
| `Leilão de Fração` (Credito) | Cash from selling the fraction (qty, unit price, value) | cash of the matching fraction |
| `Atualização` | Position snapshot: quantity held at that date | cross-check, not an event |
| `Transferência` | Moves quantity between tickers (e.g. KLBN11 → KLBN3 + KLBN4) | needs asset conversion design |
| `Direito de Subscrição`, `Direitos de Subscrição - Não Exercido`, `Cessão de Direitos` (+ `- Solicitada`) | FII subscription rights (tickers ending in 12), no value | ignore for positions |
| `COMPRA / VENDA`, `VENCIMENTO/RESGATE SALDO EM CONTA`, `PAGAMENTO DE JUROS` | CDB/LCA purchase, maturity and interest, with unit price and value | fixed income module |
| `Compra` | Tesouro Direto purchase (unit price 4293.13 × 0.11 = 472.24) | Tesouro |
| `Transferência - Liquidação` | Settlement of trades | ignore (use Negociação) |
| `Rendimento`, `Dividendo`, `Juros Sobre Capital Próprio`, `Juros` | Payouts, same as the payouts report | cross-check |

A fraction event is a **trio**: bonus/reverse split credit → `Fração em Ativos` debit →
`Leilão de Fração` cash, a few days to weeks apart. The importer groups them by asset and
quantity.

## Out of scope for now
- Watched folder in `~/Downloads` (import automatically on download): possible later with
  `launchd`.
- Open Finance / direct B3 integration.
