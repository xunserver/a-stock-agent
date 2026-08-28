import { describe, expect, it } from "vitest"

import { isoDate, monthGrid, shiftMonth, WEEKDAY_LABELS } from "./month-grid"

describe("monthGrid", () => {
  it("从周天起排，并补齐前后月份", () => {
    const cells = monthGrid(2026, 8)
    expect(WEEKDAY_LABELS).toEqual(["日", "一", "二", "三", "四", "五", "六"])
    expect(cells[0]).toEqual({ date: "2026-07-26", day: 26, inMonth: false })
    expect(cells[6]).toEqual({ date: "2026-08-01", day: 1, inMonth: true })
    expect(cells.find((cell) => cell.date === "2026-08-28")).toEqual({
      date: "2026-08-28",
      day: 28,
      inMonth: true,
    })
    expect(cells.at(-1)?.inMonth).toBe(false)
    expect(cells).toHaveLength(42)
  })
})

describe("shiftMonth", () => {
  it("跨年", () => {
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 })
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 })
  })
})

describe("isoDate", () => {
  it("补零", () => {
    expect(isoDate(2026, 8, 3)).toBe("2026-08-03")
  })
})
