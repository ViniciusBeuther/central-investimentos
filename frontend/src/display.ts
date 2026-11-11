import { money } from "./format";

const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

/** Formatters that respect the "hide values" switch. */
export type Display = { brl: (n: number) => string; int: (n: number) => string };

export const makeDisplay = (hide: boolean): Display => ({
  brl: (n) => (hide ? "R$ •••" : money(n)),
  int: (n) => (hide ? "•••••" : integer.format(n)),
});
