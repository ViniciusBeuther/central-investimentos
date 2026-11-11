import type { Display } from "../display";
import { t } from "../strings";
import type { Overview } from "../types";
import { Kpi, Needs } from "./ui";

const pct0 = (n: number) => `${n < 0 ? "−" : ""}${Math.abs(n).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
const pct1 = (n: number) => `${n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

export function Indicators({ o, d }: { o: Overview; d: Display }) {
  const market = Math.max(0, Math.min(100, o.appreciation_share));
  const bars = o.payouts.months;
  const barMax = Math.max(...bars.map((b) => b.total), 1);
  const big = o.largest_position;
  const limit = big?.limit ?? 10;
  const scaleMax = big ? Math.max(limit * 1.5, big.weight * 1.1) : limit * 1.5;
  const over = !!big && big.weight > limit;

  return (
    <section aria-label="Indicadores" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(280px, 100%), 1fr))", gap: 16 }}>
      <Kpi label={t.kpi.total} index="01">
        <div className="num"><span className="cur">R$</span>{d.int(o.total)}</div>
        <div className="sub">{t.kpi.totalSub} {d.brl(o.contributed)}</div>
      </Kpi>

      <Kpi label={t.kpi.return12} index="02"><Needs text={t.needs.history} /></Kpi>

      <Kpi label={t.kpi.origin} index="03">
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="num">{pct0(o.appreciation_share)}</span><span className="sub">{t.kpi.originSub}</span>
        </div>
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", height: 12, borderRadius: 999, overflow: "hidden", gap: 2, background: "var(--sf2)" }}>
            <div style={{ width: `${100 - market}%`, background: "var(--c-rf)" }} />
            <div style={{ width: `${market}%`, background: "var(--ac)" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13, flexWrap: "wrap" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--c-rf)" }} /><span className="mu">{t.kpi.contributions}</span> {d.brl(o.contributed)}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--ac)" }} /><span className="mu">{t.kpi.appreciation}</span> {d.brl(o.appreciation)}</span>
          </div>
        </div>
      </Kpi>

      <Kpi label={t.kpi.payouts12} index="04">
        <div className="num"><span className="cur">R$</span>{d.int(o.payouts.total_12m)}</div>
        <div className="sub">
          {t.kpi.thisMonth} <strong style={{ color: "var(--tx)" }}>{d.brl(o.payouts.this_month)}</strong> · {t.kpi.average} {d.brl(o.payouts.monthly_average)}{t.kpi.perMonth}
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 44, marginTop: "auto" }} aria-hidden="true">
          {bars.map((b, i) => {
            const [year, month] = b.month.split("-");
            return (
              <div
                key={b.month}
                title={`${t.months[Number(month) - 1]}/${year.slice(2)}: ${d.brl(b.total)}`}
                style={{ flex: 1, height: `${Math.max(2, (b.total / barMax) * 100)}%`, borderRadius: "4px 4px 1px 1px", background: i === bars.length - 1 ? "var(--ac)" : "var(--ac-soft)" }}
              />
            );
          })}
        </div>
      </Kpi>

      <Kpi label={t.kpi.drawdown} index="05"><Needs text={t.needs.history} /></Kpi>
      <Kpi label={t.kpi.reserve} index="06"><Needs text={t.needs.reserve} /></Kpi>

      <Kpi label={t.kpi.largest} index="07" warn={over}>
        {big ? (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span className="num">{pct1(big.weight)}</span>
              <span className="num-s" style={{ color: "var(--mu)" }}>{big.ticker}</span>
            </div>
            <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="track" aria-hidden="true">
                <div className="fill" style={{ width: `${(big.weight / scaleMax) * 100}%`, background: over ? "var(--am)" : "var(--ac)" }} />
                <div className="mark" style={{ left: `${(limit / scaleMax) * 100}%` }} />
              </div>
              <div className="sub" style={{ fontSize: 12 }}>
                {t.kpi.limitPerAsset} {limit}% · <span className={over ? "am" : "up"} style={{ fontWeight: 600 }}>{over ? t.kpi.aboveLimit : t.kpi.withinLimit}</span>
              </div>
            </div>
          </>
        ) : (
          <Needs text={t.needs.targets} />
        )}
      </Kpi>

      <Kpi label={t.kpi.deviation} index="08"><Needs text={t.needs.targets} /></Kpi>
    </section>
  );
}
