import { describe, expect, it } from "vitest"

import {
  MIN_BARS,
  builtInOverlays,
  countBarsInDays,
  fmtNum,
  fmtPct,
  fmtPrice,
  toSeriesData,
} from "@/components/charts/daily-k-chart-model"

describe("daily K chart model", () => {
  it("formats quote values consistently", () => {
    expect(fmtPrice(12.3)).toBe("12.30")
    expect(fmtPct(1.25)).toBe("+1.25%")
    expect(fmtPct(-1.25)).toBe("-1.25%")
    expect(fmtNum(12_000)).toBe("1.20万")
    expect(fmtPrice(null)).toBe("—")
  })

  it("keeps at least the minimum number of bars for range presets", () => {
    expect(
      countBarsInDays(
        [
          {
            trade_date: "2026-01-01",
            open: 1,
            high: 1,
            low: 1,
            close: 1,
            volume: 1,
          },
          {
            trade_date: "2026-01-02",
            open: 1,
            high: 1,
            low: 1,
            close: 1,
            volume: 1,
          },
        ],
        1
      )
    ).toBe(MIN_BARS)
  })

  it("converts valid bars and skips incomplete candles", () => {
    const palette = { gainSoft: "gain", lossSoft: "loss" } as Parameters<
      typeof toSeriesData
    >[1]
    const series = toSeriesData(
      [
        {
          trade_date: "2026-01-01",
          open: 10,
          high: 12,
          low: 9,
          close: 11,
          volume: 2,
        },
        {
          trade_date: "2026-01-02",
          open: null,
          high: 12,
          low: 9,
          close: 11,
          volume: 2,
        },
      ],
      palette
    )
    expect(series.candles).toEqual([
      { time: "2026-01-01", open: 10, high: 12, low: 9, close: 11 },
    ])
    expect(series.volumes[0]).toMatchObject({ value: 2, color: "gain" })
    expect(series.byTime.has("2026-01-02")).toBe(false)
  })

  it("preserves indicator visibility and close-line color", () => {
    const overlays = builtInOverlays(
      ["close", "ma5"],
      { foreground: "foreground" } as Parameters<typeof builtInOverlays>[1],
      [
        { time: "2026-01-01", close: 10 },
        { time: "2026-01-02", close: 11 },
      ]
    )
    expect(overlays.find((item) => item.id === "close")).toMatchObject({
      color: "foreground",
      visible: true,
    })
    expect(overlays.find((item) => item.id === "ma10")?.visible).toBe(false)
  })
})
