import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { Allocation } from "./components/Allocation";
import { Header } from "./components/Header";
import { Indicators } from "./components/Indicators";
import { Panel, Needs } from "./components/ui";
import { Sectors } from "./components/Sectors";
import { makeDisplay } from "./display";
import { t } from "./strings";
import type { DataQuality, Overview, Portfolio } from "./types";

// Remembers small per-viewer choices (theme, hidden values). Never required to work.
function stored(key: string, fallback = false): boolean {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v === "1"; } catch { return fallback; }
}
function remember(key: string, value: boolean) {
  try { localStorage.setItem(key, value ? "1" : "0"); } catch { /* private mode: ignore */ }
}

export default function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [quality, setQuality] = useState<DataQuality | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [dark, setDark] = useState(() => stored("dark", true));
  const [hide, setHide] = useState(() => stored("hide"));

  const load = useCallback(() => {
    Promise.all([api.overview(), api.portfolio(), api.dataQuality()])
      .then(([o, p, q]) => { setOverview(o); setPortfolio(p); setQuality(q); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(load, [load]);

  async function refreshQuotes() {
    setRefreshing(true);
    setMessage(null);
    try {
      const result = await api.refreshQuotes();
      const failed = Object.keys(result.failures);
      setMessage(result.skipped ? t.refreshSkipped : failed.length ? `${t.refreshFailed}: ${failed.join(", ")}` : null);
      load();
    } catch (e) {
      setMessage(String(e));
    } finally {
      setRefreshing(false);
    }
  }

  const d = useMemo(() => makeDisplay(hide), [hide]);

  if (error) return <div className="app"><div className="wrap"><p>{t.error}: {error}</p></div></div>;
  if (!overview || !portfolio) return <div className="app"><div className="wrap"><p>{t.loading}</p></div></div>;

  const alerts = overview.alerts;
  return (
    <div className={`app theme-${dark ? "dark" : "light"}`}>
      <div className="wrap" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <Header
          quotesAsOf={overview.quotes_as_of}
          dataStatus={quality?.status ?? null}
          hide={hide} dark={dark} refreshing={refreshing}
          onHide={() => { remember("hide", !hide); setHide(!hide); }}
          onTheme={() => { remember("dark", !dark); setDark(!dark); }}
          onRefresh={refreshQuotes}
        />
        {message && <span className="chip am" role="status" style={{ alignSelf: "flex-start" }}>{message}</span>}

        <nav className="tabs" aria-label="Telas">
          <button className="tab on" type="button" aria-current="page">{t.tabs.overview}</button>
          {[t.tabs.stocks, t.tabs.fiis, t.tabs.discipline].map((name) => (
            <button key={name} className="tab" type="button" aria-disabled="true" title={t.tabs.nextStep}>
              {name} <span className="soon">{t.tabs.soon}</span>
            </button>
          ))}
        </nav>

        {alerts.length > 0 ? (
          <section className="card" aria-label={t.alertsLabel} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px 16px", padding: "14px 18px", borderColor: "var(--am-ln)", background: "linear-gradient(var(--am-soft), var(--am-soft)), var(--sf)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--am)", fontWeight: 700, fontSize: 14 }}>
              <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l9.5 17h-19L12 3z" /><path d="M12 10v4M12 17.5v.5" /></svg>
              {alerts.length} {alerts.length > 1 ? t.alertsMany : t.alertsOne}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {alerts.map((a) => (
                <span key={a.text} className="chip am" style={{ height: "auto", minHeight: 28, whiteSpace: "normal", padding: "4px 11px" }}>{a.text}</span>
              ))}
            </div>
          </section>
        ) : (
          <section className="card" style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", fontWeight: 600, fontSize: 14 }}>
            <svg className="ic" style={{ color: "var(--up)" }} viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
            {t.allGood}
          </section>
        )}

        <Indicators o={overview} d={d} />

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(520px, 100%), 1fr))", gap: 16 }}>
          <Allocation allocation={overview.allocation} />
          <Sectors positions={portfolio.positions} total={overview.total} />
        </section>

        <Panel title={t.timeline.title} subtitle={t.timeline.subtitle}><Needs text={t.needs.history} /></Panel>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(520px, 100%), 1fr))", gap: 16 }}>
          <Panel title={t.contribution.title} subtitle={t.contribution.subtitle}><Needs text={t.contribution.needs} /></Panel>
          <Panel title={t.calendar.title} subtitle={t.calendar.subtitle}><Needs text={t.calendar.needs} /></Panel>
        </section>

        <footer style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: "8px 24px", fontSize: 12, color: "var(--mu)", paddingTop: 4 }}>
          <span>{t.footer}</span>
          <span>{t.footerNote}</span>
        </footer>
      </div>
    </div>
  );
}
