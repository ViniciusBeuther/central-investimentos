import { dateTime } from "../format";
import { t } from "../strings";
import { Icon } from "./ui";

type Props = {
  quotesAsOf: string | null;
  dataStatus: "ok" | "attention" | null;
  hide: boolean;
  dark: boolean;
  refreshing: boolean;
  onHide: () => void;
  onTheme: () => void;
  onRefresh: () => void;
};

const EYE = "M3 12s4-6 9-6 9 6 9 6-4 6-9 6-9-6-9-6z";
const MOON = "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z";
const REFRESH = "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? t.goodMorning : h < 18 ? t.goodAfternoon : t.goodEvening;
}

export function Header(p: Props) {
  const hideLabel = p.hide ? t.show : t.hide;
  const themeLabel = p.dark ? t.themeLight : t.themeDark;
  return (
    <header style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <div className="dotbg" style={{ width: 52, height: 52, borderRadius: 16, border: "1px solid var(--ln)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ac)", flex: "none", backgroundColor: "var(--sf)" }}>
          <svg className="ic" style={{ width: 28, height: 28 }} viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 12 L17 7" /><path d="M12 3v2M21 12h-2M12 21v-2M3 12h2" /><circle cx="12" cy="12" r="1.5" />
          </svg>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: "'Bricolage Grotesque', Inter, system-ui, sans-serif", fontSize: 28, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.05 }}>{t.appTitle}</h1>
          <div className="sub">{greeting()} {t.motto}</div>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {p.dataStatus && (
          <span className={`chip ${p.dataStatus === "ok" ? "up" : "am"}`}>{p.dataStatus === "ok" ? t.dataOk : t.dataAttention}</span>
        )}
        <span className="chip">{p.quotesAsOf ? `${t.quotesAsOf} ${dateTime(p.quotesAsOf)}` : t.quotesNone}</span>
        <button className="btn icon ghost" type="button" aria-label={hideLabel} title={hideLabel} onClick={p.onHide}>
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true">
            <path d={EYE} /><circle cx="12" cy="12" r="2.5" />{p.hide && <path d="M3 3l18 18" />}
          </svg>
        </button>
        <button className="btn icon ghost" type="button" aria-label={themeLabel} title={themeLabel} onClick={p.onTheme}>
          <Icon d={MOON} />
        </button>
        <button className="btn pri" type="button" onClick={p.onRefresh} disabled={p.refreshing}>
          <Icon d={REFRESH} />{p.refreshing ? t.refreshing : t.refreshQuotes}
        </button>
      </div>
    </header>
  );
}
