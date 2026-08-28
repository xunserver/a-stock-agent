import type { FinancialReport } from "@/lib/api"

export const PERIOD_ENDS = ["03-31", "06-30", "09-30", "12-31"] as const

export type MetricKey =
  | "eps"
  | "bps"
  | "revenue"
  | "net_profit"
  | "roe"
  | "gross_margin"
  | "net_margin"
  | "debt_ratio"

export type MetricConfig = {
  key: MetricKey
  label: string
  cumulative?: boolean
  yoyField?: "revenue_yoy" | "net_profit_yoy"
  format: "num" | "pct" | "share"
}

export const FINANCIAL_METRICS: MetricConfig[] = [
  { key: "eps", label: "每股收益", format: "share" },
  { key: "bps", label: "每股净资产", format: "share" },
  {
    key: "revenue",
    label: "营收",
    cumulative: true,
    yoyField: "revenue_yoy",
    format: "num",
  },
  {
    key: "net_profit",
    label: "净利润",
    cumulative: true,
    yoyField: "net_profit_yoy",
    format: "num",
  },
  { key: "roe", label: "ROE", format: "pct" },
  { key: "gross_margin", label: "毛利率", format: "pct" },
  { key: "net_margin", label: "净利率", format: "pct" },
  { key: "debt_ratio", label: "资产负债率", format: "pct" },
]

export type MetricComparisons = Record<
  MetricKey,
  { yoy: number | null; qoq: number | null }
>

export function formatReportPeriod(row: FinancialReport): string {
  if (row.report_type) {
    return row.report_type
  }
  return row.report_date ?? "—"
}

export function reportKey(row: FinancialReport): string {
  return `${row.report_date}-${row.report_type ?? ""}`
}

export function buildComparisons(
  reports: FinancialReport[]
): Map<string, MetricComparisons> {
  const byDate = new Map(
    reports
      .filter((report) => report.report_date)
      .map((report) => [report.report_date, report])
  )
  const result = new Map<string, MetricComparisons>()

  for (const report of reports) {
    if (!report.report_date) {
      continue
    }
    const comparisons = emptyComparisons()
    for (const metric of FINANCIAL_METRICS) {
      comparisons[metric.key] = {
        yoy: computeYoy(report, metric, byDate),
        qoq: computeQoq(report, metric, byDate),
      }
    }
    result.set(report.report_date, comparisons)
  }

  return result
}

export function emptyComparisons(): MetricComparisons {
  return {
    eps: { yoy: null, qoq: null },
    bps: { yoy: null, qoq: null },
    revenue: { yoy: null, qoq: null },
    net_profit: { yoy: null, qoq: null },
    roe: { yoy: null, qoq: null },
    gross_margin: { yoy: null, qoq: null },
    net_margin: { yoy: null, qoq: null },
    debt_ratio: { yoy: null, qoq: null },
  }
}

function computeYoy(
  report: FinancialReport,
  metric: MetricConfig,
  byDate: Map<string, FinancialReport>
): number | null {
  if (metric.yoyField) {
    const apiValue = report[metric.yoyField]
    if (apiValue != null && Number.isFinite(apiValue)) {
      return apiValue
    }
  }

  const current = metricValue(
    report,
    metric.key,
    byDate,
    "yoy",
    Boolean(metric.cumulative)
  )
  const priorYear = findPriorYearReport(report, byDate)
  const base = metricValue(
    priorYear,
    metric.key,
    byDate,
    "yoy",
    Boolean(metric.cumulative)
  )
  return pctChange(current, base)
}

function computeQoq(
  report: FinancialReport,
  metric: MetricConfig,
  byDate: Map<string, FinancialReport>
): number | null {
  const current = metricValue(
    report,
    metric.key,
    byDate,
    "qoq",
    Boolean(metric.cumulative)
  )
  const priorPeriod = findPriorPeriodReport(report, byDate)
  let base: number | null
  if (!priorPeriod) {
    base = null
  } else if (metric.cumulative && priorPeriod.report_date?.endsWith("-12-31")) {
    base = q4IncrementalValue(priorPeriod, metric.key, byDate)
  } else if (metric.cumulative) {
    base = incrementalValue(priorPeriod, metric.key, byDate)
  } else {
    base = metricValue(priorPeriod, metric.key, byDate, "qoq", false)
  }
  return pctChange(current, base)
}

function metricValue(
  report: FinancialReport | undefined,
  key: MetricKey,
  byDate: Map<string, FinancialReport>,
  mode: "yoy" | "qoq",
  cumulative: boolean
): number | null {
  if (!report) {
    return null
  }
  const raw = report[key]
  if (raw == null || !Number.isFinite(raw)) {
    return null
  }
  if (!cumulative || mode === "yoy") {
    return raw
  }
  return incrementalValue(report, key, byDate)
}

function incrementalValue(
  report: FinancialReport,
  key: MetricKey,
  byDate: Map<string, FinancialReport>
): number | null {
  const raw = report[key]
  if (raw == null || !Number.isFinite(raw) || !report.report_date) {
    return raw ?? null
  }

  const md = report.report_date.slice(5)
  const periodIndex = PERIOD_ENDS.indexOf(md as (typeof PERIOD_ENDS)[number])
  if (periodIndex <= 0) {
    return raw
  }

  const year = report.report_date.slice(0, 4)
  const previous = byDate.get(`${year}-${PERIOD_ENDS[periodIndex - 1]}`)
  const previousRaw = previous?.[key]
  if (previousRaw == null || !Number.isFinite(previousRaw)) {
    return raw
  }
  return raw - previousRaw
}

function q4IncrementalValue(
  report: FinancialReport,
  key: MetricKey,
  byDate: Map<string, FinancialReport>
): number | null {
  const raw = report[key]
  if (raw == null || !Number.isFinite(raw) || !report.report_date) {
    return raw ?? null
  }

  const year = report.report_date.slice(0, 4)
  const q3 = byDate.get(`${year}-09-30`)
  const q3Raw = q3?.[key]
  if (q3Raw == null || !Number.isFinite(q3Raw)) {
    return raw
  }
  return raw - q3Raw
}

function findPriorYearReport(
  report: FinancialReport,
  byDate: Map<string, FinancialReport>
): FinancialReport | undefined {
  if (!report.report_date) {
    return undefined
  }
  const year = Number(report.report_date.slice(0, 4))
  const md = report.report_date.slice(5)
  return byDate.get(`${year - 1}-${md}`)
}

function findPriorPeriodReport(
  report: FinancialReport,
  byDate: Map<string, FinancialReport>
): FinancialReport | undefined {
  if (!report.report_date) {
    return undefined
  }

  const year = report.report_date.slice(0, 4)
  const md = report.report_date.slice(5)
  const periodIndex = PERIOD_ENDS.indexOf(md as (typeof PERIOD_ENDS)[number])
  if (periodIndex < 0) {
    return undefined
  }
  if (periodIndex === 0) {
    return byDate.get(`${Number(year) - 1}-12-31`)
  }
  return byDate.get(`${year}-${PERIOD_ENDS[periodIndex - 1]}`)
}

function pctChange(
  current: number | null,
  base: number | null
): number | null {
  if (
    current == null ||
    base == null ||
    !Number.isFinite(current) ||
    !Number.isFinite(base) ||
    base === 0
  ) {
    return null
  }
  return ((current - base) / Math.abs(base)) * 100
}

export function pctClass(value: number | null): string {
  if (value == null) {
    return "text-muted-foreground"
  }
  if (value > 0) {
    return "text-gain"
  }
  if (value < 0) {
    return "text-loss"
  }
  return "text-muted-foreground"
}

export function fmtPct(value: number | null | undefined, signed = true): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  const sign = signed && value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

export function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  const abs = Math.abs(value)
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`
  }
  return value.toFixed(2)
}

export function fmtShare(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  return value.toFixed(2)
}

export function formatMetricValue(
  metric: MetricConfig,
  value: number | null | undefined
): string {
  if (metric.format === "pct") {
    return fmtPct(value, false)
  }
  if (metric.format === "share") {
    return fmtShare(value)
  }
  return fmtNum(value)
}
