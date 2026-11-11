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
  - payout identical to another one (possible duplicate)
- **Check against B3**: if the position export is available, compare quantities per asset
  with the computed ones and flag divergences.

## Out of scope for now
- Watched folder in `~/Downloads` (import automatically on download): possible later with
  `launchd`.
- Open Finance / direct B3 integration.
