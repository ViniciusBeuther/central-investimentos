import type { ReactNode } from "react";
import { t } from "../strings";

export function Icon({ d, size }: { d: string; size?: number }) {
  return (
    <svg className="ic" style={size ? { width: size, height: size } : undefined} viewBox="0 0 24 24" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

/** KPI card of the design: label + index on top, content below. `warn` tints it amber. */
export function Kpi({ label, index, warn, children }: { label: string; index: string; warn?: boolean; children: ReactNode }) {
  return (
    <article className={`card kpi${warn ? " warn" : ""}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="lbl">{label}</span>
        <span className="idx">{index}</span>
      </div>
      {children}
    </article>
  );
}

/** Empty state: says what is missing instead of showing invented numbers. */
export function Needs({ text }: { text: string }) {
  return (
    <div className="empty">
      <strong>{t.needs.title}</strong>
      <span>{text}</span>
    </div>
  );
}

/** Large card with a title and a one-line description. */
export function Panel({ title, subtitle, aside, children }: { title: string; subtitle?: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <article className="card" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h2 className="h2">{title}</h2>
          {subtitle && <div className="sub">{subtitle}</div>}
        </div>
        {aside}
      </div>
      {children}
    </article>
  );
}
