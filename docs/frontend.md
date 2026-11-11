# Frontend

React + Vite + TypeScript in `frontend/src`, http://localhost:3000 (Vite proxies `/api` to the API).
Typecheck: `docker compose exec web npx tsc --noEmit`.

## Design source
Claude Design artifact "Central de Controle de Investimentos". The artifact now holds one board,
`Main.dc.html` ("Tela 1 · Visão geral"): cards, Bricolage Grotesque + Inter, dark theme by default
with a light theme. An earlier pass wrongly implemented a different version ("Vitral", since
removed from the artifact); it was replaced.
- `styles.css` is the design's CSS taken as is (same class names: `.card`, `.kpi`, `.chip`,
  `.track`...), plus a few additions at the bottom. Do not restyle piecemeal.
- Fonts (Bricolage Grotesque, Inter) load from Google Fonts in `index.html`. Accepted by the user.

## Files
| File | Role |
|---|---|
| `types.ts` / `api.ts` | Shapes of API responses and one typed function per endpoint |
| `format.ts` / `display.ts` | pt-BR formatting; `display.ts` respects the "hide values" switch |
| `strings.ts` | Every user-facing string (bilingual UI later = swap this file) |
| `App.tsx` | Page layout, data loading, theme and hide switches (kept in localStorage) |
| `components/Header.tsx` | Title, quote freshness, data-quality chip, hide/theme/refresh buttons |
| `components/Indicators.tsx` | The eight KPI cards (01 to 08) |
| `components/Allocation.tsx` | Current vs target bars per class |
| `components/Sectors.tsx` | Squarified treemap of the risk assets (by type until sectors exist) |
| `components/ui.tsx` | `Kpi`, `Panel`, `Needs` (empty state), `Icon` |

## What shows real data and what is waiting
The design computed everything from sample data in the browser. Here the numbers come from the
API (`/api/overview`, `/api/portfolio`, `/api/data-quality`), and a panel without data says what
it needs instead of showing invented numbers (`Needs`).

| Panel | Status | Needs |
|---|---|---|
| Patrimônio total, De onde veio, Proventos 12 meses, Maior posição | real data | (max-position limit is a constant, 10%) |
| Alocação atual vs. meta | real; target bars empty | allocation targets per class |
| Por setor | real, grouped by asset type | sector per asset |
| Retorno 12 meses, Queda desde o pico, Linha do tempo | waiting | daily portfolio history, CDI and Ibovespa series |
| Reserva de emergência | waiting | monthly cost of living, which products are reserve |
| Desvio da meta, Aporte do mês | waiting | targets per asset, planned contribution, thesis status |
| Próximos eventos | waiting | CVM document collector |
| "Editar dados" drawer | not built | write endpoints and tables for targets, sectors, thesis, parameters |
