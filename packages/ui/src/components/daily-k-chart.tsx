import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts"

import { Button } from "@/components/ui/button"
import { Toggle } from "@/components/ui/toggle"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { changeTextClass } from "@/lib/change"
import {
  candleSeriesOptions,
  chartOptions,
  overlaySeriesOptions,
  readChartPalette,
  timeToDateKey,
  volumeSeriesOptions,
  type ChartPalette,
} from "@/lib/chart-theme"
import { emaSeries, smaSeries } from "@/lib/indicators"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

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

const MIN_BARS = 20
const EMPTY_BARS: Candle[] = []
const EMPTY_OVERLAYS: ChartLineOverlay[] = []
const EMPTY_MARKERS: ChartMarker[] = []

const INDICATORS = [
  { id: "close", label: "收盘", kind: "close", color: "#737373" },
  { id: "ma5", label: "MA5", kind: "ma", period: 5, color: "#d97706" },
  { id: "ma10", label: "MA10", kind: "ma", period: 10, color: "#2563eb" },
  { id: "ma20", label: "MA20", kind: "ma", period: 20, color: "#7c3aed" },
  { id: "ema12", label: "EMA12", kind: "ema", period: 12, color: "#db2777" },
  { id: "ema26", label: "EMA26", kind: "ema", period: 26, color: "#0d9488" },
] as const

const PERIODS = [
  { id: "daily", label: "日K" },
  { id: "weekly", label: "周K" },
  { id: "yearly", label: "年K" },
] as const

const RANGE_PRESETS = [
  { id: "week", label: "最近一周", days: 7 },
  { id: "month", label: "最近一个月", days: 30 },
  { id: "quarter", label: "最近一个季度", days: 90 },
  { id: "year", label: "最近一年", days: 365 },
] as const

type PeriodId = (typeof PERIODS)[number]["id"]

function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function fmtPrice(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  return value.toFixed(2)
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

function fmtNum(value: number | null | undefined): string {
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

function subtractDays(dateKey: string, days: number): string {
  const [year, month, day] = dateKey.split("-").map(Number)
  const date = new Date(year, month - 1, day)
  date.setDate(date.getDate() - days)
  const nextYear = date.getFullYear()
  const nextMonth = String(date.getMonth() + 1).padStart(2, "0")
  const nextDay = String(date.getDate()).padStart(2, "0")
  return `${nextYear}-${nextMonth}-${nextDay}`
}

function countBarsInDays(bars: Candle[], days: number): number {
  if (bars.length === 0) {
    return MIN_BARS
  }
  const cutoffKey = subtractDays(bars[bars.length - 1].trade_date, days)
  let count = 0
  for (let index = bars.length - 1; index >= 0; index -= 1) {
    if (bars[index].trade_date >= cutoffKey) {
      count += 1
    } else {
      break
    }
  }
  return Math.max(MIN_BARS, count || MIN_BARS)
}

function toSeriesData(
  bars: Candle[],
  palette: ChartPalette
): {
  candles: CandlestickData<Time>[]
  volumes: HistogramData<Time>[]
  byTime: Map<string, Candle>
} {
  const candles: CandlestickData<Time>[] = []
  const volumes: HistogramData<Time>[] = []
  const byTime = new Map<string, Candle>()
  for (const bar of bars) {
    const open = num(bar.open)
    const high = num(bar.high)
    const low = num(bar.low)
    const close = num(bar.close)
    if (open == null || high == null || low == null || close == null) {
      continue
    }
    const time = bar.trade_date
    candles.push({ time, open, high, low, close })
    volumes.push({
      time,
      value: num(bar.volume) ?? 0,
      color: close >= open ? palette.gainSoft : palette.lossSoft,
    })
    byTime.set(time, bar)
  }
  return { candles, volumes, byTime }
}

export function DailyKChart({
  bars,
  barsWeekly = EMPTY_BARS,
  barsYearly = EMPTY_BARS,
  overlays = EMPTY_OVERLAYS,
  markers = EMPTY_MARKERS,
}: {
  bars: Candle[]
  barsWeekly?: Candle[]
  barsYearly?: Candle[]
  overlays?: ChartLineOverlay[]
  markers?: ChartMarker[]
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null)
  const overlayRefs = useRef(new Map<string, ISeriesApi<"Line">>())
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const applyingRange = useRef(false)
  const fitPending = useRef(true)

  const [palette, setPalette] = useState<ChartPalette | null>(() =>
    typeof document === "undefined"
      ? null
      : readChartPalette(document.documentElement)
  )
  const [periodId, setPeriodId] = useState<PeriodId>(
    () => readUiPrefs().chartPeriod
  )
  const [hoverKey, setHoverKey] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(0)
  const [indicatorIds, setIndicatorIds] = useState<string[]>(
    () => readUiPrefs().chartIndicators
  )

  function selectPeriod(id: PeriodId) {
    setPeriodId(id)
  }

  function toggleIndicator(id: string, next: boolean) {
    setIndicatorIds((current) =>
      next
        ? current.includes(id)
          ? current
          : [...current, id]
        : current.filter((item) => item !== id)
    )
  }

  useEffect(() => {
    patchUiPrefs({
      chartPeriod: periodId,
      chartIndicators: indicatorIds,
    })
  }, [periodId, indicatorIds])

  const periodBars =
    periodId === "weekly"
      ? barsWeekly
      : periodId === "yearly"
        ? barsYearly
        : bars

  const usable = useMemo(
    () =>
      periodBars.filter(
        (bar) =>
          num(bar.high) !== null &&
          num(bar.low) !== null &&
          num(bar.open) !== null &&
          num(bar.close) !== null
      ),
    [periodBars]
  )
  const series = useMemo(
    () => (palette ? toSeriesData(usable, palette) : null),
    [usable, palette]
  )
  const pricePoints = useMemo(
    () =>
      (series?.candles ?? []).map((bar) => ({
        time: String(bar.time),
        close: bar.close,
      })),
    [series]
  )
  const builtInOverlays = useMemo((): ChartLineOverlay[] => {
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
  }, [indicatorIds, palette, pricePoints])
  const mergedOverlays = useMemo(
    () => [...builtInOverlays, ...overlays],
    [builtInOverlays, overlays]
  )
  const dataKey = `${periodId}:${usable[0]?.trade_date ?? ""}:${usable[usable.length - 1]?.trade_date ?? ""}:${usable.length}`

  useEffect(() => {
    fitPending.current = true
    setHoverKey(null)
  }, [dataKey])

  useLayoutEffect(() => {
    const host = hostRef.current
    if (!host || usable.length === 0) {
      return
    }

    const nextPalette = readChartPalette(host)
    setPalette(nextPalette)

    const chart = createChart(
      host,
      chartOptions(nextPalette, { includeParsers: true })
    )
    const candles = chart.addSeries(
      CandlestickSeries,
      candleSeriesOptions(nextPalette),
      0
    )
    const volume = chart.addSeries(
      HistogramSeries,
      volumeSeriesOptions(nextPalette),
      1
    )
    volume.priceScale().applyOptions({
      scaleMargins: { top: 0.18, bottom: 0 },
    })
    const panes = chart.panes()
    if (panes.length >= 2) {
      panes[0].setStretchFactor(3)
      panes[1].setStretchFactor(1)
    }

    chartRef.current = chart
    candleRef.current = candles
    volumeRef.current = volume

    const onCrosshair = (param: { time?: Time }) => {
      if (param.time == null) {
        setHoverKey(null)
        return
      }
      setHoverKey(timeToDateKey(param.time))
    }
    const onRange = () => {
      const range = chart.timeScale().getVisibleLogicalRange()
      if (range) {
        setVisibleCount(Math.max(1, Math.round(range.to - range.from)))
      }
    }
    const markCustom = () => {
      if (applyingRange.current) {
        return
      }
      fitPending.current = false
    }
    chart.subscribeCrosshairMove(onCrosshair)
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange)
    host.addEventListener("pointerdown", markCustom)
    host.addEventListener("wheel", markCustom, { passive: true })

    const themeRoot = document.documentElement
    const syncTheme = () => {
      const current = chartRef.current
      const node = hostRef.current
      if (!current || !node) {
        return
      }
      const next = readChartPalette(node)
      setPalette(next)
      current.applyOptions(chartOptions(next))
      candleRef.current?.applyOptions(candleSeriesOptions(next))
      volumeRef.current?.applyOptions(volumeSeriesOptions(next))
    }
    const themeObs = new MutationObserver(syncTheme)
    themeObs.observe(themeRoot, {
      attributes: true,
      attributeFilter: ["class"],
    })

    return () => {
      themeObs.disconnect()
      host.removeEventListener("pointerdown", markCustom)
      host.removeEventListener("wheel", markCustom)
      chart.unsubscribeCrosshairMove(onCrosshair)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange)
      overlayRefs.current.clear()
      markersRef.current = null
      candleRef.current = null
      volumeRef.current = null
      chartRef.current = null
      chart.remove()
    }
  }, [usable.length === 0, periodId])

  useEffect(() => {
    const chart = chartRef.current
    const candles = candleRef.current
    const volume = volumeRef.current
    if (!chart || !candles || !volume || !series) {
      return
    }
    candles.setData(series.candles)
    volume.setData(series.volumes)

    const overlayMap = overlayRefs.current
    const nextIds = new Set(mergedOverlays.map((item) => item.id))
    for (const [id, line] of overlayMap) {
      if (!nextIds.has(id)) {
        chart.removeSeries(line)
        overlayMap.delete(id)
      }
    }
    for (const overlay of mergedOverlays) {
      let line = overlayMap.get(overlay.id)
      if (overlay.visible === false) {
        if (line) {
          chart.removeSeries(line)
          overlayMap.delete(overlay.id)
        }
        continue
      }
      const options = overlaySeriesOptions(
        overlay.color,
        overlay.lineWidth,
        true
      )
      if (!line) {
        line = chart.addSeries(LineSeries, options, 0)
        overlayMap.set(overlay.id, line)
      } else {
        line.applyOptions(options)
      }
      line.setData(overlay.data)
    }

    if (markers.length > 0) {
      const payload = markers as SeriesMarker<Time>[]
      if (!markersRef.current) {
        markersRef.current = createSeriesMarkers(candles, payload)
      } else {
        markersRef.current.setMarkers(payload)
      }
    } else if (markersRef.current) {
      markersRef.current.setMarkers([])
    }
  }, [series, mergedOverlays, markers])

  useEffect(() => {
    const chart = chartRef.current
    if (
      !chart ||
      !series ||
      series.candles.length === 0 ||
      !fitPending.current
    ) {
      return
    }
    applyingRange.current = true
    chart.timeScale().fitContent()
    const timer = window.setTimeout(() => {
      applyingRange.current = false
      fitPending.current = false
      const range = chart.timeScale().getVisibleLogicalRange()
      if (range) {
        setVisibleCount(Math.max(1, Math.round(range.to - range.from)))
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [series, dataKey])

  function applyZoom(factor: number) {
    const chart = chartRef.current
    const range = chart?.timeScale().getVisibleLogicalRange()
    if (!chart || !range) {
      return
    }
    const minBars = Math.min(MIN_BARS, usable.length)
    const span = Math.max(minBars, (range.to - range.from) * factor)
    const maxSpan = Math.max(usable.length, minBars)
    const nextSpan = Math.min(maxSpan, span)
    const mid = (range.from + range.to) / 2
    fitPending.current = false
    chart.timeScale().setVisibleLogicalRange({
      from: mid - nextSpan / 2,
      to: mid + nextSpan / 2,
    })
  }

  function applyRangePreset(days: number) {
    const chart = chartRef.current
    if (!chart || usable.length === 0) {
      return
    }
    const minBars = Math.min(MIN_BARS, usable.length)
    const span = Math.min(
      usable.length,
      Math.max(minBars, countBarsInDays(usable, days))
    )
    fitPending.current = false
    applyingRange.current = true
    chart.timeScale().setVisibleLogicalRange({
      from: usable.length - span,
      to: usable.length,
    })
    setVisibleCount(span)
    window.setTimeout(() => {
      applyingRange.current = false
    }, 0)
  }

  const periodLabel =
    PERIODS.find((item) => item.id === periodId)?.label ?? "日K"

  if (usable.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <ToggleGroup
          value={[periodId]}
          onValueChange={(next) => {
            const id = next[0]
            if (id === "daily" || id === "weekly" || id === "yearly") {
              selectPeriod(id)
            }
          }}
          variant="outline"
          size="sm"
          spacing={0}
        >
          {PERIODS.map((item) => (
            <ToggleGroupItem key={item.id} value={item.id}>
              {item.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <p className="text-sm text-muted-foreground">
          还没有{periodLabel}。同步行情后会画在这里。
        </p>
      </div>
    )
  }

  const active =
    (hoverKey && series?.byTime.get(hoverKey)) || usable[usable.length - 1]
  const yang = active
    ? (num(active.close) ?? 0) >= (num(active.open) ?? 0)
    : true
  const change = active?.pct_chg ?? (yang ? 1 : -1)
  const shown =
    visibleCount > 0 ? Math.min(visibleCount, usable.length) : usable.length
  const minBars = Math.min(MIN_BARS, usable.length)
  const canZoomIn = shown > minBars
  const canZoomOut = shown < usable.length

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ToggleGroup
          value={[periodId]}
          onValueChange={(next) => {
            const id = next[0]
            if (id === "daily" || id === "weekly" || id === "yearly") {
              selectPeriod(id)
            }
          }}
          variant="outline"
          size="sm"
          spacing={0}
        >
          {PERIODS.map((item) => (
            <ToggleGroupItem key={item.id} value={item.id}>
              {item.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="flex flex-wrap items-center justify-end gap-1">
          {RANGE_PRESETS.map((preset) => (
            <Button
              key={preset.id}
              type="button"
              variant="outline"
              size="xs"
              onClick={() => applyRangePreset(preset.days)}
            >
              {preset.label}
            </Button>
          ))}
          <Button
            type="button"
            variant="outline"
            size="xs"
            disabled={!canZoomOut}
            onClick={() => applyZoom(1.35)}
          >
            缩小
          </Button>
          <Button
            type="button"
            variant="outline"
            size="xs"
            disabled={!canZoomIn}
            onClick={() => applyZoom(0.7)}
          >
            放大
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        {INDICATORS.map((item) => {
          const overlay = builtInOverlays.find((row) => row.id === item.id)
          const point = overlay?.data.find(
            (row) => row.time === active.trade_date
          )
          const pressed = indicatorIds.includes(item.id)
          const swatch =
            item.kind === "close" && palette ? palette.foreground : item.color
          return (
            <Toggle
              key={item.id}
              size="sm"
              variant="outline"
              pressed={pressed}
              onPressedChange={(next) => {
                toggleIndicator(item.id, next)
              }}
              aria-label={`${item.label}${pressed ? " 显示中" : " 已隐藏"}`}
              className={cn(!pressed && "opacity-45")}
            >
              <span
                className="size-1.5 rounded-full"
                style={{ backgroundColor: swatch }}
              />
              <span>{item.label}</span>
              <span
                className="font-normal tabular-nums"
                style={{ color: swatch }}
              >
                {fmtPrice(point?.value)}
              </span>
            </Toggle>
          )
        })}
      </div>
      {active ? (
        <div className="rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
          <div className="grid w-full grid-cols-[7.25rem_4.25rem_3.25rem_repeat(8,minmax(0,1fr))] items-baseline gap-x-2 text-xs leading-4">
            <span className="font-medium tabular-nums">
              {active.trade_date}
            </span>
            <span
              className={cn(
                "font-medium tabular-nums",
                changeTextClass(active.pct_chg)
              )}
            >
              {fmtPct(active.pct_chg)}
            </span>
            <span
              className={cn("tabular-nums", changeTextClass(active.pct_chg))}
            >
              {active.change_amount != null
                ? fmtPrice(active.change_amount)
                : "—"}
            </span>
            <QuoteStat
              label="开"
              value={fmtPrice(active.open)}
              className={changeTextClass(change)}
            />
            <QuoteStat
              label="高"
              value={fmtPrice(active.high)}
              className={changeTextClass(change)}
            />
            <QuoteStat
              label="低"
              value={fmtPrice(active.low)}
              className={changeTextClass(change)}
            />
            <QuoteStat
              label="收"
              value={fmtPrice(active.close)}
              className={changeTextClass(change)}
            />
            <QuoteStat label="量" value={fmtNum(active.volume)} />
            <QuoteStat label="额" value={fmtNum(active.amount)} />
            <QuoteStat
              label="换手"
              value={
                active.turnover != null ? `${fmtPrice(active.turnover)}%` : "—"
              }
            />
            <QuoteStat
              label="振幅"
              value={
                active.amplitude != null
                  ? `${fmtPrice(active.amplitude)}%`
                  : "—"
              }
            />
          </div>
        </div>
      ) : null}
      <div
        ref={hostRef}
        className="h-[min(36rem,56vh)] w-full overflow-hidden rounded-lg"
        onWheel={(event) => event.stopPropagation()}
      />
      <p className="text-xs text-muted-foreground">
        {periodLabel} 显示 {shown} / {usable.length}{" "}
        根。阳线红色，阴线绿色。点收盘或均线按钮切换显示。鼠标移到 K
        线上查看当期开高低收；范围按钮、滚轮或缩放按钮调整视野，拖动平移。
      </p>
    </div>
  )
}

function QuoteStat({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <span className="inline-flex min-w-0 items-baseline gap-1">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className={cn("min-w-0 truncate tabular-nums", className)}>
        {value}
      </span>
    </span>
  )
}
