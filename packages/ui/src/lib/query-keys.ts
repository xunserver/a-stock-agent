/** Stable, feature-scoped keys for TanStack Query caches. */
export const queryKeys = {
  system: {
    all: ["system"] as const,
    health: () => ["system", "health"] as const,
    status: (pool?: string) => ["system", "status", pool ?? "default"] as const,
  },
  pools: {
    all: ["pools"] as const,
    list: () => ["pools", "list"] as const,
    members: (pool = "default", includeRemoved = false) => ["pools", "members", pool, includeRemoved] as const,
  },
  stocks: {
    all: ["stocks"] as const,
    list: () => ["stocks", "list"] as const,
    detail: (code: string) => ["stocks", "detail", code] as const,
    news: (code: string) => ["stocks", "news", code] as const,
    events: (code: string, kind: string) => ["stocks", "events", code, kind] as const,
    financial: (code: string, sheet: string, reportDate: string) => ["stocks", "financial", code, sheet, reportDate] as const,
  },
  calendar: {
    all: ["calendar"] as const,
    markets: () => ["calendar", "markets"] as const,
    overview: () => ["calendar", "overview"] as const,
    month: (market: string, year: number, month: number) => ["calendar", "month", market, year, month] as const,
    grid: (year?: number, month?: number) => ["calendar", "grid", year, month] as const,
  },
  qlib: {
    all: ["qlib"] as const,
    overview: (pool: string) => ["qlib", "overview", pool] as const,
    runs: (pool: string) => ["qlib", "runs", pool] as const,
    run: (runId: string) => ["qlib", "run", runId] as const,
  },
  analyses: {
    all: ["analyses"] as const,
    list: (input?: { pool?: string; code?: string }) => ["analyses", "list", input?.pool, input?.code] as const,
    detail: (code: string, date: string, runId?: string) => ["analyses", "detail", code, date, runId] as const,
  },
  jobs: {
    all: ["jobs"] as const,
    list: (filters?: Record<string, string | number | undefined>) => ["jobs", "list", filters] as const,
    detail: (jobId: string) => ["jobs", "detail", jobId] as const,
  },
  automations: {
    all: ["automations"] as const,
    list: () => ["automations", "list"] as const,
    detail: (id: string) => ["automations", "detail", id] as const,
    catalog: () => ["automations", "catalog"] as const,
    runs: (id: string, date?: string) => ["automations", "runs", id, date] as const,
  },
  settings: {
    all: ["settings"] as const,
    detail: () => ["settings", "detail"] as const,
    catalog: () => ["settings", "catalog"] as const,
  },
} as const
