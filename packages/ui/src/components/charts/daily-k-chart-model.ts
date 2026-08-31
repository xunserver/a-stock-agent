import type { CandlestickData, HistogramData, Time } from "lightweight-charts"

import type { ChartPalette } from "@/lib/chart-theme"
import { emaSeries, smaSeries } from "@/lib/indicators"

export type Candle = {
  trade_date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  amount?: number | null
  pct_chg?: number | null
  turnover?: number | null
  amplitude?: number | null
  change_amount?: number | null
}

export type ChartLineOverlay = {
  id: string
  color: string
  data: { time: string; value?: number }[]
  lineWidth?: number
  visible?: boolean
}

export type ChartMarker = {
  time: string
  position: "aboveBar" | "belowBar" | "inBar"
  shape: "arrowUp" | "arrowDown" | "circle" | "square"
  color: string
  text?: string
  id?: string
}

export const MIN_BARS = 20

export const INDICATORS = [
  { id: "close", label: "收盘", kind: "close", color: "#737373" },
  { id: "ma5", label: "MA5", kind: "ma", period: 5, color: "#d97706" },
  { id: "ma10", label: "MA10", kind: "ma", period: 10, color: "#2563eb" },
  { id: "ma20", label: "MA20", kind: "ma", period: 20, color: "#7c3aed" },
  { id: "ema12", label: "EMA12", kind: "ema", period: 12, color: "#db2777" },
  { id: "ema26", label: "EMA26", kind: "ema", period: 26, color: "#0d9488" },
] as const

export const PERIODS = [
  { id: "daily", label: "日K" },
  { id: "weekly", label: "周K" },
  { id: "yearly", label: "年K" },
] as const

export const RANGE_PRESETS = [
  { id: "week", label: "最近一周", days: 7 },
  { id: "month", label: "最近一个月", days: 30 },
  { id: "quarter", label: "最近一个季度", days: 90 },
  { id: "year", label: "最近一年", days: 365 },
] as const

export type PeriodId = (typeof PERIODS)[number]["id"]

export function finiteNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

export function fmtPrice(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(2)
}

export function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`
}

export function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  const abs = Math.abs(value)
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(2)
}

export function isUsableCandle(bar: Candle): boolean {
  return [bar.open, bar.high, bar.low, bar.close].every(
    (value) => finiteNumber(value) !== null
  )
}

function subtractDays(dateKey: string, days: number): string {
  const [year, month, day] = dateKey.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  date.setDate(date.getDate() - days)
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-")
}

export function countBarsInDays(bars: Candle[], days: number): number {
  if (bars.length === 0) return MIN_BARS
  const cutoffKey = subtractDays(bars[bars.length - 1].trade_date, days)
  let count = 0
  for (let index = bars.length - 1; index >= 0; index -= 1) {
    if (bars[index].trade_date >= cutoffKey) count += 1
    else break
  }
  return Math.max(MIN_BARS, count || MIN_BARS)
}

export function toSeriesData(bars: Candle[], palette: ChartPalette) {
  const candles: CandlestickData<Time>[] = []
  const volumes: HistogramData<Time>[] = []
  const byTime = new Map<string, Candle>()
  for (const bar of bars) {
    const open = finiteNumber(bar.open)
    const high = finiteNumber(bar.high)
    const low = finiteNumber(bar.low)
    const close = finiteNumber(bar.close)
    if (open == null || high == null || low == null || close == null) continue
    const time = bar.trade_date
    candles.push({ time, open, high, low, close })
    volumes.push({
      time,
      value: finiteNumber(bar.volume) ?? 0,
      color: close >= open ? palette.gainSoft : palette.lossSoft,
    })
    byTime.set(time, bar)
  }
  return { candles, volumes, byTime }
}

export function builtInOverlays(
  indicatorIds: string[],
  palette: ChartPalette | null,
  pricePoints: { time: string; close: number }[]
): ChartLineOverlay[] {
  const enabled = new Set(indicatorIds)
  return INDICATORS.map((item) => ({
    id: item.id,
    color: item.kind === "close" && palette ? palette.foreground : item.color,
    visible: enabled.has(item.id),
    data:
      item.kind === "close"
        ? pricePoints.map((row) => ({ time: row.time, value: row.close }))
        : item.kind === "ma"
          ? smaSeries(pricePoints, item.period)
          : emaSeries(pricePoints, item.period),
  }))
}

export function chartDataKey(periodId: PeriodId, bars: Candle[]): string {
  return `${periodId}:${bars[0]?.trade_date ?? ""}:${bars[bars.length - 1]?.trade_date ?? ""}:${bars.length}`
}
