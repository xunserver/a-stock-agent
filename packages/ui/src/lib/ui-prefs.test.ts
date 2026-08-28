import { beforeEach, describe, expect, it } from "vitest"

import {
  DEFAULT_UI_PREFS,
  UI_PREFS_KEY,
  parseUiPrefs,
  patchUiPrefs,
  readUiPrefs,
} from "@/lib/ui-prefs"

describe("parseUiPrefs", () => {
  it("缺字段时用默认值", () => {
    expect(parseUiPrefs({})).toEqual(DEFAULT_UI_PREFS)
  })

  it("只接受合法的筛选、周期和均线", () => {
    expect(
      parseUiPrefs({
        quoteFilter: "fill",
        chartPeriod: "monthly",
        chartIndicators: ["close", "bogus", "ema12", "close"],
        infoOpen: { quotes: true, valuation: "yes" },
        detailTab: "financials",
      })
    ).toEqual({
      quoteFilter: "all",
      chartPeriod: "daily",
      chartIndicators: ["close", "ema12"],
      infoOpen: {
        quotes: true,
        valuation: false,
      },
      detailTab: "financials",
      poolId: null,
      pickedCode: null,
      jobTrackerCollapsed: false,
    })
  })

  it("均线全无效时回到默认组合", () => {
    expect(parseUiPrefs({ chartIndicators: ["nope"] }).chartIndicators).toEqual(
      DEFAULT_UI_PREFS.chartIndicators
    )
  })

  it("空均线列表表示全部关闭，不会回到默认", () => {
    expect(parseUiPrefs({ chartIndicators: [] }).chartIndicators).toEqual([])
  })

  it("只接受合法的池 id 和六位代码", () => {
    expect(
      parseUiPrefs({
        poolId: "hs-300",
        pickedCode: "600519",
      })
    ).toMatchObject({ poolId: "hs-300", pickedCode: "600519" })
    expect(
      parseUiPrefs({
        poolId: "bad id",
        pickedCode: "SH600519",
      })
    ).toMatchObject({ poolId: null, pickedCode: null })
  })
})

describe("ui prefs storage", () => {
  beforeEach(() => window.localStorage.clear())

  it("刷新后能读回筛选、K 线周期、均线和折叠", () => {
    patchUiPrefs({
      quoteFilter: "sync",
      chartPeriod: "weekly",
      chartIndicators: ["close", "ema12", "ema26"],
      infoOpen: { quotes: true, valuation: true },
      detailTab: "financials",
      poolId: "core",
      pickedCode: "000001",
    })
    expect(readUiPrefs()).toEqual({
      quoteFilter: "sync",
      chartPeriod: "weekly",
      chartIndicators: ["close", "ema12", "ema26"],
      infoOpen: { quotes: true, valuation: true },
      detailTab: "financials",
      poolId: "core",
      pickedCode: "000001",
      jobTrackerCollapsed: false,
    })
  })

  it("局部更新不会清掉其它选择", () => {
    patchUiPrefs({ quoteFilter: "sync", chartPeriod: "yearly" })
    patchUiPrefs({ chartIndicators: ["ma5"] })
    expect(readUiPrefs()).toMatchObject({
      quoteFilter: "sync",
      chartPeriod: "yearly",
      chartIndicators: ["ma5"],
    })
    patchUiPrefs({ poolId: "core" })
    expect(readUiPrefs().chartIndicators).toEqual(["ma5"])
  })

  it("损坏的数据会安全回退到默认", () => {
    window.localStorage.setItem(UI_PREFS_KEY, "{")
    expect(readUiPrefs()).toEqual(DEFAULT_UI_PREFS)
  })
})
