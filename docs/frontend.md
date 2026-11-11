# Frontend

React + Vite + TypeScript in `frontend/src`, http://localhost:3000 (Vite proxies `/api` to the API).

| File | Role |
|---|---|
| `types.ts` | Shapes of the API responses (mirror of `docs/api.md`) |
| `api.ts` | Typed `fetch` wrapper: one function per endpoint |
| `format.ts` | pt-BR formatting for money, percent, quantity, date |
| `strings.ts` | Every user-facing string, so a bilingual UI is a swap of this file |
| `App.tsx` | Home: totals cards, refresh-quotes button, distribution, positions table |

The first version is deliberately plain: it proves the data path end to end. The design from
Claude Design replaces the markup in `App.tsx` (and splits it into pages); `types`, `api`,
`format` and `strings` stay. Typecheck: `docker compose exec web npx tsc --noEmit`.
