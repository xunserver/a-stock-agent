import type { FinancialReport } from "@/lib/api"
import { PERIOD_ENDS, pctClass, fmtPct } from "@/lib/financial-metrics"

const COMPANION_SUFFIXES = ["_YOY", "_QOQ", "_MOM", "_TZ"] as const

export type StatementRow = {
  key: string
  label: string
  value: number | string | null
  kind?: "amount" | "percent" | string
  yoy: number | null
  qoq: number | null
}

export { pctClass, fmtPct }

export function isCompanionKey(key: string): boolean {
  return COMPANION_SUFFIXES.some((suffix) => key.endsWith(suffix))
}

export function findPriorPeriodDate(
  reportDate: string,
  reports: FinancialReport[]
): string | null {
  const dates = reports
    .map((report) => report.report_date)
    .filter((date): date is string => Boolean(date))
    .sort()
    .reverse()
  const index = dates.indexOf(reportDate)
  if (index < 0 || index >= dates.length - 1) {
    return null
  }
  return dates[index + 1] ?? null
}

function numericValue(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value === "string") {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function pctChange(current: number | null, base: number | null): number | null {
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

function priorSameYearDate(reportDate: string): string | null {
  const md = reportDate.slice(5)
  const periodIndex = PERIOD_ENDS.indexOf(md as (typeof PERIOD_ENDS)[number])
  if (periodIndex <= 0) {
    return null
  }
  return `${reportDate.slice(0, 4)}-${PERIOD_ENDS[periodIndex - 1]}`
}

function incrementalValue(
  reportDate: string,
  key: string,
  payload: Record<string, number | string | null>,
  priorSameYearPayload: Record<string, number | string | null> | null
): number | null {
  const raw = numericValue(payload[key])
  if (raw == null) {
    return null
  }
  const priorDate = priorSameYearDate(reportDate)
  if (!priorDate || !priorSameYearPayload) {
    return raw
  }
  const previousRaw = numericValue(priorSameYearPayload[key])
  if (previousRaw == null) {
    return raw
  }
  return raw - previousRaw
}

function q4IncrementalValue(
  reportDate: string,
  key: string,
  payload: Record<string, number | string | null>,
  priorSameYearPayload: Record<string, number | string | null> | null
): number | null {
  const raw = numericValue(payload[key])
  if (raw == null) {
    return null
  }
  const q3Payload =
    priorSameYearPayload && reportDate.endsWith("-12-31")
      ? priorSameYearPayload
      : null
  const q3Raw = q3Payload ? numericValue(q3Payload[key]) : null
  if (q3Raw == null) {
    return raw
  }
  return raw - q3Raw
}

function comparisonValue(
  sheet: "balance" | "profit" | "cashflow",
  reportDate: string,
  key: string,
  payload: Record<string, number | string | null>,
  priorSameYearPayload: Record<string, number | string | null> | null,
  mode: "yoy" | "qoq"
): number | null {
  const raw = numericValue(payload[key])
  if (raw == null) {
    return null
  }
  if (sheet === "balance" || mode === "yoy") {
    return raw
  }
  return incrementalValue(reportDate, key, payload, priorSameYearPayload)
}

function priorPeriodBaseValue(
  sheet: "balance" | "profit" | "cashflow",
  priorReportDate: string,
  key: string,
  priorPayload: Record<string, number | string | null>,
  priorSameYearPayload: Record<string, number | string | null> | null
): number | null {
  if (sheet === "balance") {
    return numericValue(priorPayload[key])
  }
  if (priorReportDate.endsWith("-12-31")) {
    return q4IncrementalValue(
      priorReportDate,
      key,
      priorPayload,
      priorSameYearPayload
    )
  }
  return incrementalValue(
    priorReportDate,
    key,
    priorPayload,
    priorSameYearPayload
  )
}

export function buildStatementRows(
  items: Array<{
    key: string
    label: string
    value: number | string | null
    kind?: string
    yoy?: number | null
    qoq?: number | null
  }>,
  options: {
    sheet: "balance" | "profit" | "cashflow"
    reportDate: string
    payload: Record<string, number | string | null>
    priorPayload?: Record<string, number | string | null> | null
    priorReportDate?: string | null
    priorSameYearPayload?: Record<string, number | string | null> | null
  }
): StatementRow[] {
  const {
    sheet,
    reportDate,
    payload,
    priorPayload,
    priorReportDate,
    priorSameYearPayload,
  } = options

  return items
    .filter((item) => !isCompanionKey(item.key) && item.kind !== "percent")
    .map((item) => {
      const yoy =
        numericValue(item.yoy ?? payload[`${item.key}_YOY`]) ??
        null
      let qoq =
        numericValue(item.qoq ?? payload[`${item.key}_QOQ`]) ??
        numericValue(payload[`${item.key}_MOM`])

      if (qoq == null && priorPayload && priorReportDate) {
        const current = comparisonValue(
          sheet,
          reportDate,
          item.key,
          payload,
          priorSameYearPayload ?? null,
          "qoq"
        )
        const base = priorPeriodBaseValue(
          sheet,
          priorReportDate,
          item.key,
          priorPayload,
          priorSameYearPayload ?? null
        )
        qoq = pctChange(current, base)
      }

      return {
        key: item.key,
        label: item.label,
        value: item.value,
        kind: item.kind,
        yoy,
        qoq,
      }
    })
}

export function formatStatementAmount(
  value: number | string | null | undefined
): string {
  if (value == null || value === "") {
    return "—"
  }
  if (typeof value === "string") {
    return value
  }
  if (!Number.isFinite(value)) {
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
