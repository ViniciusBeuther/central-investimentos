const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const qty = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 });
const when = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

export const money = (n: number) => brl.format(n);
export const percent = (n: number) => pct.format(n);
export const quantity = (n: number) => qty.format(n);
export const dateTime = (iso: string) => when.format(new Date(iso));
