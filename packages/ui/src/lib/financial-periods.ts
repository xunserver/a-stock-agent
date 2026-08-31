export const PERIOD_ENDS = ["03-31", "06-30", "09-30", "12-31"] as const

export function numericValue(
  value: number | string | null | undefined
): number | null {
  if (value == null || value === "") return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function pctChange(
  current: number | null,
  base: number | null
): number | null {
  if (current == null || base == null || base === 0) return null
  return ((current - base) / Math.abs(base)) * 100
}

export function previousFiscalPeriodDate(reportDate: string): string | null {
  const year = Number(reportDate.slice(0, 4))
  const index = PERIOD_ENDS.indexOf(
    reportDate.slice(5) as (typeof PERIOD_ENDS)[number]
  )
  if (!Number.isFinite(year) || index < 0) return null
  if (index === 0) return `${year - 1}-${PERIOD_ENDS[3]}`
  return `${year}-${PERIOD_ENDS[index - 1]}`
}

export function previousSameYearPeriodDate(
  reportDate: string | null | undefined
): string | null {
  if (!reportDate) return null
  const previous = previousFiscalPeriodDate(reportDate)
  if (!previous || previous.slice(0, 4) !== reportDate.slice(0, 4)) return null
  return previous
}

export function priorYearPeriodDate(reportDate: string): string | null {
  const year = Number(reportDate.slice(0, 4))
  const period = reportDate.slice(5)
  if (
    !Number.isFinite(year) ||
    !PERIOD_ENDS.includes(period as (typeof PERIOD_ENDS)[number])
  ) {
    return null
  }
  return `${year - 1}-${period}`
}

export function incrementalPeriodValue(
  reportDate: string,
  current: number | null,
  previousCumulative: number | null
): number | null {
  if (current == null) return null
  return previousSameYearPeriodDate(reportDate) && previousCumulative != null
    ? current - previousCumulative
    : current
}
