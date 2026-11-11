import { t } from "../strings";
import type { Overview } from "../types";
import { Panel } from "./ui";

const COLORS = { rf: "var(--c-rf)", acoes: "var(--c-ac)", fii: "var(--c-fii)" } as const;
const pct1 = (n: number) => `${n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

/** Current vs target allocation per class, as paired bars. Targets are null until registered. */
export function Allocation({ allocation }: { allocation: Overview["allocation"] }) {
  const scaleMax = Math.max(...allocation.map((a) => Math.max(a.weight, a.target ?? 0))) * 1.18 || 1;
  const hasTargets = allocation.some((a) => a.target !== null);
  const legend = (
    <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--mu)", alignItems: "center" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "var(--mu)" }} />{t.alloc.current}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, border: "1.5px dashed var(--mu)", boxSizing: "border-box" }} />{t.alloc.target}</span>
    </div>
  );

  return (
    <Panel title={t.alloc.title} subtitle={t.alloc.subtitle} aside={legend}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
        {allocation.map((a) => {
          const color = COLORS[a.class];
          const diff = a.target === null ? null : a.weight - a.target;
          return (
            <div key={a.class} style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-end", height: 210, width: "100%", justifyContent: "center", borderBottom: "1px solid var(--ln)" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", gap: 6, height: "100%", width: "46%", maxWidth: 64 }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{pct1(a.weight)}</span>
                  <div style={{ width: "100%", height: `${(a.weight / scaleMax) * 82}%`, background: color, borderRadius: "10px 10px 2px 2px" }} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", gap: 6, height: "100%", width: "46%", maxWidth: 64 }}>
                  <span className="mu" style={{ fontWeight: 600, fontSize: 13 }}>{a.target === null ? "—" : `${a.target}%`}</span>
                  {a.target !== null && (
                    <div style={{ width: "100%", height: `${(a.target / scaleMax) * 82}%`, border: `2px dashed ${color}`, borderBottom: 0, borderRadius: "10px 10px 0 0", boxSizing: "border-box" }} />
                  )}
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, textAlign: "center" }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{t.classes[a.class]}</span>
                <span className="chip">{diff === null ? t.alloc.noTarget : `${diff > 0 ? "+" : diff < 0 ? "−" : ""}${Math.abs(diff).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} pp`}</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="sub" style={{ fontSize: 12, borderTop: "1px solid var(--ln)", paddingTop: 12 }}>
        {hasTargets ? t.alloc.explain : t.alloc.explainNoTargets}
      </div>
    </Panel>
  );
}
