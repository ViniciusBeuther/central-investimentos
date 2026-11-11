// Shapes of the API responses (see docs/api.md). Keep in sync with backend/app/routes.py.
export type Position = {
  ticker: string;
  name: string | null;
  type: string;
  quantity: number;
  average_price: number;
  cost: number;
  realized_profit: number;
  warnings: string[];
  price: number | null;
  quoted_at: string | null;
  market_value: number;
  unrealized_profit: number | null;
  valued_by: "quote" | "cost";
  share: number;
};

export type Portfolio = {
  totals: {
    invested: number;
    market_value: number;
    unrealized_profit: number;
    realized_profit: number;
    payouts_received: number;
    open_positions: number;
    quoted_positions: number;
    quotes_as_of: string | null;
  };
  by_type: { type: string; invested: number; market_value: number; share: number }[];
  positions: Position[];
};

export type RefreshResult = {
  skipped: boolean;
  reason?: string;
  fetched: number;
  failures: Record<string, string>;
};

export type Overview = {
  quotes_as_of: string | null;
  total: number;
  contributed: number;
  appreciation: number;
  appreciation_share: number;
  payouts: { months: { month: string; total: number }[]; total_12m: number; this_month: number; monthly_average: number };
  largest_position: { ticker: string; weight: number; limit: number } | null;
  allocation: { class: "rf" | "acoes" | "fii"; value: number; weight: number; target: number | null }[];
  alerts: { kind: string; text: string }[];
  missing: string[];
};

export type DataQuality = { status: "ok" | "attention"; checks: { name: string; status: string; detail: string }[] };
