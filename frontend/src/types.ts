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
