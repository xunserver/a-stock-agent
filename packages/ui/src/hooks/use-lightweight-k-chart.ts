import { useEffect, useLayoutEffect, useRef, type RefObject } from "react"
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts"

import type {
  Candle,
  ChartLineOverlay,
  ChartMarker,
  PeriodId,
} from "@/components/charts/daily-k-chart-model"
import {
  MIN_BARS,
  countBarsInDays,
  toSeriesData,
} from "@/components/charts/daily-k-chart-model"
import {
  candleSeriesOptions,
  chartOptions,
  overlaySeriesOptions,
  readChartPalette,
  timeToDateKey,
  volumeSeriesOptions,
  type ChartPalette,
} from "@/lib/chart-theme"

type SeriesData = ReturnType<typeof toSeriesData>

export function useLightweightKChart({
  hostRef,
  empty,
  periodId,
  bars,
  series,
  overlays,
  markers,
  dataKey,
  onPalette,
  onHoverKey,
  onVisibleCount,
}: {
  hostRef: RefObject<HTMLDivElement | null>
  empty: boolean
  periodId: PeriodId
  bars: Candle[]
  series: SeriesData | null
  overlays: ChartLineOverlay[]
  markers: ChartMarker[]
  dataKey: string
  onPalette: (palette: ChartPalette) => void
  onHoverKey: (key: string | null) => void
  onVisibleCount: (count: number) => void
}) {
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null)
  const overlayRefs = useRef(new Map<string, ISeriesApi<"Line">>())
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const applyingRange = useRef(false)
  const fitPending = useRef(true)

  useEffect(() => {
    fitPending.current = true
    onHoverKey(null)
  }, [dataKey])

  useLayoutEffect(() => {
    const host = hostRef.current
    if (!host || empty) return

    const palette = readChartPalette(host)
    onPalette(palette)
    const chart = createChart(
      host,
      chartOptions(palette, { includeParsers: true })
    )
    const candles = chart.addSeries(
      CandlestickSeries,
      candleSeriesOptions(palette),
      0
    )
    const volume = chart.addSeries(
      HistogramSeries,
      volumeSeriesOptions(palette),
      1
    )
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.18, bottom: 0 } })
    const panes = chart.panes()
    if (panes.length >= 2) {
      panes[0].setStretchFactor(3)
      panes[1].setStretchFactor(1)
    }
    chartRef.current = chart
    candleRef.current = candles
    volumeRef.current = volume

    const onCrosshair = (param: { time?: Time }) =>
      onHoverKey(param.time == null ? null : timeToDateKey(param.time))
    const onRange = () => {
      const range = chart.timeScale().getVisibleLogicalRange()
      if (range) onVisibleCount(Math.max(1, Math.round(range.to - range.from)))
    }
    const markCustom = () => {
      if (!applyingRange.current) fitPending.current = false
    }
    chart.subscribeCrosshairMove(onCrosshair)
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange)
    host.addEventListener("pointerdown", markCustom)
    host.addEventListener("wheel", markCustom, { passive: true })

    const themeRoot = document.documentElement
    const syncTheme = () => {
      const current = chartRef.current
      const node = hostRef.current
      if (!current || !node) return
      const next = readChartPalette(node)
      onPalette(next)
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
  }, [empty, periodId])

  useEffect(() => {
    const chart = chartRef.current
    const candles = candleRef.current
    const volume = volumeRef.current
    if (!chart || !candles || !volume || !series) return
    candles.setData(series.candles)
    volume.setData(series.volumes)

    const overlayMap = overlayRefs.current
    const nextIds = new Set(overlays.map((item) => item.id))
    for (const [id, line] of overlayMap) {
      if (!nextIds.has(id)) {
        chart.removeSeries(line)
        overlayMap.delete(id)
      }
    }
    for (const overlay of overlays) {
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
      if (!markersRef.current)
        markersRef.current = createSeriesMarkers(candles, payload)
      else markersRef.current.setMarkers(payload)
    } else if (markersRef.current) {
      markersRef.current.setMarkers([])
    }
  }, [series, overlays, markers])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !series || series.candles.length === 0 || !fitPending.current)
      return
    applyingRange.current = true
    chart.timeScale().fitContent()
    const timer = window.setTimeout(() => {
      applyingRange.current = false
      fitPending.current = false
      const range = chart.timeScale().getVisibleLogicalRange()
      if (range) onVisibleCount(Math.max(1, Math.round(range.to - range.from)))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [series, dataKey])

  return {
    applyZoom(factor: number) {
      const chart = chartRef.current
      const range = chart?.timeScale().getVisibleLogicalRange()
      if (!chart || !range) return
      const minBars = Math.min(MIN_BARS, bars.length)
      const span = Math.max(minBars, (range.to - range.from) * factor)
      const nextSpan = Math.min(Math.max(bars.length, minBars), span)
      const mid = (range.from + range.to) / 2
      fitPending.current = false
      chart.timeScale().setVisibleLogicalRange({
        from: mid - nextSpan / 2,
        to: mid + nextSpan / 2,
      })
    },
    applyRangePreset(days: number) {
      const chart = chartRef.current
      if (!chart || bars.length === 0) return
      const minBars = Math.min(MIN_BARS, bars.length)
      const span = Math.min(
        bars.length,
        Math.max(minBars, countBarsInDays(bars, days))
      )
      fitPending.current = false
      applyingRange.current = true
      chart
        .timeScale()
        .setVisibleLogicalRange({ from: bars.length - span, to: bars.length })
      onVisibleCount(span)
      window.setTimeout(() => {
        applyingRange.current = false
      }, 0)
    },
  }
}
