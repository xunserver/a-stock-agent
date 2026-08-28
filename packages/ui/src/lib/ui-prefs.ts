import { isQuoteFilter, type QuoteFilter } from "@/lib/quote-filter"

export const UI_PREFS_KEY = "astock.ui-prefs"

export type ChartPeriodId = "daily" | "weekly" | "yearly"
export type InfoSectionId = "quotes" | "valuation"
export type DetailTabId = "overview" | "financials"

export type UiPrefs = {
  quoteFilter: QuoteFilter
  chartPeriod: ChartPeriodId
  chartIndicators: string[]
  infoOpen: Record<InfoSectionId, boolean>
  detailTab: DetailTabId
  poolId: string | null
  pickedCode: string | null
  jobTrackerCollapsed: boolean
}

const CHART_PERIODS = new Set<ChartPeriodId>(["daily", "weekly", "yearly"])
const CHART_INDICATORS = new Set([
  "close",
  "ma5",
  "ma10",
  "ma20",
  "ema12",
  "ema26",
])
const DEFAULT_INDICATORS = ["close", "ma5", "ma10", "ma20"]
const POOL_ID_RE = /^[A-Za-z0-9_-]{1,32}$/
const STOCK_CODE_RE = /^\d{6}$/

export const DEFAULT_UI_PREFS: UiPrefs = {
  quoteFilter: "all",
  chartPeriod: "daily",
  chartIndicators: [...DEFAULT_INDICATORS],
  infoOpen: {
    quotes: false,
    valuation: false,
  },
  detailTab: "overview",
  poolId: null,
  pickedCode: null,
  jobTrackerCollapsed: false,
}

function isChartPeriod(value: unknown): value is ChartPeriodId {
  return typeof value === "string" && CHART_PERIODS.has(value as ChartPeriodId)
}

function parseIndicators(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [...DEFAULT_INDICATORS]
  }
  const unique = [
    ...new Set(
      value.filter(
        (item): item is string =>
          typeof item === "string" && CHART_INDICATORS.has(item)
      )
    ),
  ]
  if (value.length === 0) {
    return []
  }
  return unique.length > 0 ? unique : [...DEFAULT_INDICATORS]
}

function parseInfoOpen(value: unknown): Record<InfoSectionId, boolean> {
  const source =
    value && typeof value === "object" ? (value as Record<string, unknown>) : {}
  return {
    quotes: source.quotes === true,
    valuation: source.valuation === true,
  }
}

function parseDetailTab(value: unknown): DetailTabId {
  return value === "financials" ? "financials" : "overview"
}

function parsePoolId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null
  }
  const id = value.trim()
  return POOL_ID_RE.test(id) ? id : null
}

function parsePickedCode(value: unknown): string | null {
  if (typeof value !== "string") {
    return null
  }
  const code = value.trim()
  return STOCK_CODE_RE.test(code) ? code : null
}

export function parseUiPrefs(value: unknown): UiPrefs {
  const source =
    value && typeof value === "object" ? (value as Record<string, unknown>) : {}
  const quoteFilter =
    typeof source.quoteFilter === "string" && isQuoteFilter(source.quoteFilter)
      ? source.quoteFilter
      : DEFAULT_UI_PREFS.quoteFilter
  return {
    quoteFilter,
    chartPeriod: isChartPeriod(source.chartPeriod)
      ? source.chartPeriod
      : DEFAULT_UI_PREFS.chartPeriod,
    chartIndicators: parseIndicators(source.chartIndicators),
    infoOpen: parseInfoOpen(source.infoOpen),
    detailTab: parseDetailTab(source.detailTab),
    poolId: parsePoolId(source.poolId),
    pickedCode: parsePickedCode(source.pickedCode),
    jobTrackerCollapsed: source.jobTrackerCollapsed === true,
  }
}

export function readUiPrefs(): UiPrefs {
  if (typeof window === "undefined") {
    return { ...DEFAULT_UI_PREFS, infoOpen: { ...DEFAULT_UI_PREFS.infoOpen } }
  }
  try {
    return parseUiPrefs(
      JSON.parse(window.localStorage.getItem(UI_PREFS_KEY) ?? "null")
    )
  } catch {
    return { ...DEFAULT_UI_PREFS, infoOpen: { ...DEFAULT_UI_PREFS.infoOpen } }
  }
}

export function patchUiPrefs(patch: Partial<UiPrefs>): UiPrefs {
  const current = readUiPrefs()
  const next: UiPrefs = {
    ...current,
    ...patch,
    infoOpen: patch.infoOpen
      ? { ...current.infoOpen, ...patch.infoOpen }
      : current.infoOpen,
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(UI_PREFS_KEY, JSON.stringify(next))
  }
  return next
}
