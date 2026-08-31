import { useEffect, useMemo, useRef, useState } from "react"

import {
  ChartPeriodPicker,
  ChartToolbar,
  IndicatorLegend,
  QuoteStats,
} from "@/components/charts/daily-k-chart-view"
import {
  builtInOverlays,
  chartDataKey,
  isUsableCandle,
  PERIODS,
  toSeriesData,
  type Candle,
  type ChartLineOverlay,
  type ChartMarker,
  type PeriodId,
} from "@/components/charts/daily-k-chart-model"
import { useLightweightKChart } from "@/hooks/use-lightweight-k-chart"
import { readChartPalette, type ChartPalette } from "@/lib/chart-theme"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"

export type { Candle, ChartLineOverlay, ChartMarker }

const EMPTY_BARS: Candle[] = []
const EMPTY_OVERLAYS: ChartLineOverlay[] = []
const EMPTY_MARKERS: ChartMarker[] = []

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

  useEffect(() => {
    patchUiPrefs({ chartPeriod: periodId, chartIndicators: indicatorIds })
  }, [periodId, indicatorIds])

  const periodBars =
    periodId === "weekly"
      ? barsWeekly
      : periodId === "yearly"
        ? barsYearly
        : bars
  const usable = useMemo(() => periodBars.filter(isUsableCandle), [periodBars])
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
  const indicatorOverlays = useMemo(
    () => builtInOverlays(indicatorIds, palette, pricePoints),
    [indicatorIds, palette, pricePoints]
  )
  const mergedOverlays = useMemo(
    () => [...indicatorOverlays, ...overlays],
    [indicatorOverlays, overlays]
  )
  const dataKey = chartDataKey(periodId, usable)
  const chart = useLightweightKChart({
    hostRef,
    empty: usable.length === 0,
    periodId,
    bars: usable,
    series,
    overlays: mergedOverlays,
    markers,
    dataKey,
    onPalette: setPalette,
    onHoverKey: setHoverKey,
    onVisibleCount: setVisibleCount,
  })

  const periodLabel =
    PERIODS.find((item) => item.id === periodId)?.label ?? "日K"
  if (usable.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <ChartPeriodPicker periodId={periodId} onSelect={setPeriodId} />
        <p className="text-sm text-muted-foreground">
          还没有{periodLabel}。同步行情后会画在这里。
        </p>
      </div>
    )
  }

  const active =
    (hoverKey && series?.byTime.get(hoverKey)) || usable[usable.length - 1]
  const shown =
    visibleCount > 0 ? Math.min(visibleCount, usable.length) : usable.length
  const minBars = Math.min(20, usable.length)

  return (
    <div className="flex flex-col gap-2">
      <ChartToolbar
        periodId={periodId}
        onSelectPeriod={setPeriodId}
        canZoomIn={shown > minBars}
        canZoomOut={shown < usable.length}
        onApplyRange={chart.applyRangePreset}
        onZoom={chart.applyZoom}
      />
      <IndicatorLegend
        active={active}
        palette={palette}
        indicatorIds={indicatorIds}
        overlays={indicatorOverlays}
        onToggle={(id, pressed) => {
          setIndicatorIds((current) =>
            pressed
              ? current.includes(id)
                ? current
                : [...current, id]
              : current.filter((item) => item !== id)
          )
        }}
      />
      <QuoteStats active={active} />
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
