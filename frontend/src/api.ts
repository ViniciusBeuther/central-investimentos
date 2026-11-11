import type { DataQuality, Overview, Portfolio, RefreshResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

export const api = {
  portfolio: () => request<Portfolio>("/portfolio"),
  overview: () => request<Overview>("/overview"),
  dataQuality: () => request<DataQuality>("/data-quality"),
  refreshQuotes: () => request<RefreshResult>("/quotes/refresh", { method: "POST" }),
};
