import { percent } from "../format";
import { t } from "../strings";
import type { Position } from "../types";
import { Panel } from "./ui";

type Item = { name: string; value: number; tickers: string[]; color: string; family: "acoes" | "fii"; a: number };
type Tile = Item & { x: number; y: number; w: number; h: number };

// Sector is not registered yet, so tiles are asset types. Stocks on the left, FIIs on the right, as in the design.
const TYPES: Record<string, { color: string; family: "acoes" | "fii" }> = {
  stock: { color: "#A493FA", family: "acoes" },
  etf: { color: "#B6A8FF", family: "acoes" },
  fii: { color: "#E59ACA", family: "fii" },
  fiagro: { color: "#F5C0DD", family: "fii" },
};
const W = 1.9;
const H = 1;

/** Squarified treemap (Bruls et al.): keeps the tiles close to squares. Same algorithm as the design. */
function squarify(items: Item[], x: number, y: number, w: number, h: number): Tile[] {
  const out: Tile[] = [];
  const rest = items.slice();
  let row: Item[] = [];
  const worst = (r: Item[], len: number) => {
    const s = r.reduce((n, i) => n + i.a, 0);
    const mx = Math.max(...r.map((i) => i.a));
    const mn = Math.min(...r.map((i) => i.a));
    return Math.max((len * len * mx) / (s * s), (s * s) / (len * len * mn));
  };
  const lay = (r: Item[]) => {
    const s = r.reduce((n, i) => n + i.a, 0);
    if (w >= h) {
      const cw = s / h;
      let yy = y;
      r.forEach((i) => { const ih = i.a / cw; out.push({ ...i, x, y: yy, w: cw, h: ih }); yy += ih; });
      x += cw; w -= cw;
    } else {
      const rh = s / w;
      let xx = x;
      r.forEach((i) => { const iw = i.a / rh; out.push({ ...i, x: xx, y, w: iw, h: rh }); xx += iw; });
      y += rh; h -= rh;
    }
  };
  while (rest.length) {
    const len = Math.min(w, h);
    const next = rest[0];
    if (!row.length || worst([...row, next], len) <= worst(row, len)) { row.push(next); rest.shift(); }
    else { lay(row); row = []; }
  }
  if (row.length) lay(row);
  return out;
}

export function Sectors({ positions, total }: { positions: Position[]; total: number }) {
  const groups = new Map<string, Item>();
  for (const p of positions) {
    const kind = TYPES[p.type];
    if (!kind || p.market_value <= 0) continue;
    const g = groups.get(p.type) ?? { name: t.types[p.type] ?? p.type, value: 0, tickers: [], color: kind.color, family: kind.family, a: 0 };
    g.value += p.market_value;
    g.tickers.push(p.ticker);
    groups.set(p.type, g);
  }
  const all = [...groups.values()];
  const sum = all.reduce((n, i) => n + i.value, 0) || 1;
  all.forEach((i) => { i.a = (i.value / sum) * W * H; });
  const byFamily = (f: "acoes" | "fii") => all.filter((i) => i.family === f).sort((a, b) => b.value - a.value);
  const left = byFamily("acoes");
  const right = byFamily("fii");
  const leftWidth = left.reduce((n, i) => n + i.a, 0) / H;
  const tiles = [
    ...(left.length ? squarify(left, 0, 0, leftWidth, H) : []),
    ...(right.length ? squarify(right, leftWidth, 0, W - leftWidth, H) : []),
  ];
  const biggest = [...tiles].sort((a, b) => b.value - a.value)[0];
  const label = `${t.sectors.title}: ` + tiles.map((x) => `${x.name} ${percent(x.value / total)}`).join(", ");
  const legend = (
    <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--mu)", alignItems: "center" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "#A493FA" }} />{t.types.stock}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "#E59ACA" }} />{t.types.fii}</span>
    </div>
  );

  return (
    <Panel title={t.sectors.title} subtitle={t.sectors.subtitle} aside={legend}>
      <div role="img" aria-label={label} style={{ position: "relative", height: 300, margin: -3 }}>
        {tiles.map((x) => (
          <div key={x.name} title={`${x.name}: ${percent(x.value / total)} ${t.sectors.ofPortfolio}`}
            style={{ position: "absolute", left: `${(x.x / W) * 100}%`, top: `${(x.y / H) * 100}%`, width: `${(x.w / W) * 100}%`, height: `${(x.h / H) * 100}%`, padding: 3, boxSizing: "border-box" }}>
            <div style={{ width: "100%", height: "100%", borderRadius: 12, background: x.color, color: "#17112B", padding: 12, boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "space-between", overflow: "hidden" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                <span style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{x.name}</span>
                <span style={{ fontSize: 11, fontWeight: 500, opacity: 0.8, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{x.tickers.join(" · ")}</span>
              </div>
              <span style={{ fontFamily: "'Bricolage Grotesque', Inter, system-ui, sans-serif", fontWeight: 700, fontSize: 22, lineHeight: 1 }}>{percent(x.value / total)}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="sub" style={{ fontSize: 12, borderTop: "1px solid var(--ln)", paddingTop: 12 }}>
        {biggest ? `${t.sectors.biggest} ${biggest.name}, ${percent(biggest.value / total)} ${t.sectors.ofPortfolio}. ` : ""}{t.sectors.note}
      </div>
    </Panel>
  );
}
