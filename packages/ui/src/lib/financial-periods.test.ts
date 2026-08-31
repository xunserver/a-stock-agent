import { describe, expect, it } from "vitest"

import {
  incrementalPeriodValue,
  previousFiscalPeriodDate,
  previousSameYearPeriodDate,
} from "@/lib/financial-periods"
import { buildStatementRows } from "@/lib/financial-statement-rows"

describe("financial period rules", () => {
  it("crosses the year boundary without treating Q4 cumulative as one quarter", () => {
    expect(previousFiscalPeriodDate("2026-03-31")).toBe("2025-12-31")
    expect(previousSameYearPeriodDate("2026-03-31")).toBeNull()
    expect(incrementalPeriodValue("2026-03-31", 120, 400)).toBe(120)
  })

  it("compares incremental income-statement quarters from one shared rule", () => {
    const rows = buildStatementRows(
      [{ key: "total_revenue", label: "营业总收入", value: 300 }],
      {
        sheet: "profit",
        reportDate: "2026-09-30",
        payload: { total_revenue: 300 },
        priorReportDate: "2026-06-30",
        priorPayload: { total_revenue: 180 },
        priorPriorPayload: { total_revenue: 80 },
      }
    )

    // Q3 standalone=120, Q2 standalone=100, so sequential growth is 20%.
    expect(rows[0]?.qoq).toBeCloseTo(20)
  })
})
