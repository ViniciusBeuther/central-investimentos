import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { dateTime, money, percent, quantity } from "./format";
import { t } from "./strings";
import type { Portfolio } from "./types";

// Functional first version: proves the data path end to end. The visual design from
// Claude Design replaces the markup; types, api and format stay.
export default function App() {
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    api.portfolio().then(setData).catch((e) => setError(String(e)));
  }, []);
  useEffect(load, [load]);

  async function refreshQuotes() {
    setRefreshing(true);
    setMessage(null);
    try {
      const result = await api.refreshQuotes();
      const failed = Object.keys(result.failures);
      setMessage(
        result.skipped
          ? t.refreshSkipped
          : failed.length
            ? `${t.refreshFailed}: ${failed.join(", ")}`
            : null,
      );
      load();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setRefreshing(false);
    }
  }

  if (error) return <p>{t.error}: {error}</p>;
  if (!data) return <p>{t.loading}</p>;
  const { totals } = data;

  return (
    <main style={{ fontFamily: "sans-serif", padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      <h1>{t.appTitle}</h1>

      <section style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Card label={t.invested} value={money(totals.invested)} />
        <Card label={t.marketValue} value={money(totals.market_value)} />
        <Card label={t.unrealizedProfit} value={money(totals.unrealized_profit)} signed={totals.unrealized_profit} />
        <Card label={t.realizedProfit} value={money(totals.realized_profit)} signed={totals.realized_profit} />
        <Card label={t.payoutsReceived} value={money(totals.payouts_received)} />
      </section>

      <p>
        <button onClick={refreshQuotes} disabled={refreshing}>
          {refreshing ? t.refreshing : t.refreshQuotes}
        </button>{" "}
        {totals.quotes_as_of && <small>{t.quotesAsOf} {dateTime(totals.quotes_as_of)}</small>}{" "}
        {message && <small>· {message}</small>}
      </p>

      <h2>{t.byType}</h2>
      <ul>
        {data.by_type.map((row) => (
          <li key={row.type}>
            {t.types[row.type] ?? row.type}: {money(row.market_value)} ({percent(row.share)})
          </li>
        ))}
      </ul>

      <h2>{t.positions} ({data.positions.length})</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "right" }}>
            <th style={{ textAlign: "left" }}>{t.ticker}</th>
            <th>{t.quantity}</th>
            <th>{t.averagePrice}</th>
            <th>{t.price}</th>
            <th>{t.value}</th>
            <th>{t.result}</th>
            <th>{t.share}</th>
          </tr>
        </thead>
        <tbody>
          {data.positions.map((p) => (
            <tr key={p.ticker} style={{ textAlign: "right", borderTop: "1px solid #ddd" }}>
              <td style={{ textAlign: "left" }} title={p.name ?? ""}>{p.ticker}</td>
              <td>{quantity(p.quantity)}</td>
              <td>{money(p.average_price)}</td>
              <td>{p.price === null ? "—" : money(p.price)}</td>
              <td title={p.valued_by === "cost" ? t.valuedAtCost : p.quoted_at ? dateTime(p.quoted_at) : ""}>
                {money(p.market_value)}
              </td>
              <td style={{ color: color(p.unrealized_profit) }}>
                {p.unrealized_profit === null ? "—" : money(p.unrealized_profit)}
              </td>
              <td>{percent(p.share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

function color(n: number | null) {
  return n === null || n === 0 ? undefined : n > 0 ? "#127a3a" : "#b3261e";
}

function Card({ label, value, signed }: { label: string; value: string; signed?: number }) {
  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, minWidth: 160 }}>
      <small>{label}</small>
      <div style={{ fontSize: 20, fontWeight: 600, color: color(signed ?? null) }}>{value}</div>
    </div>
  );
}
