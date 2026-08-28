import { describe, expect, it } from "vitest"

import {
  filterMembersByQuotePlan,
  isQuoteFilter,
  memberNeedsSync,
  nextQuoteFilter,
} from "@/lib/quote-filter"

describe("nextQuoteFilter", () => {
  it("点另一项时取新值，而不是数组里仍排在前面的旧值", () => {
    expect(nextQuoteFilter(["all", "sync"], "all")).toBe("sync")
    expect(nextQuoteFilter(["sync"], "all")).toBe("sync")
  })

  it("取消选中时保持原筛选", () => {
    expect(nextQuoteFilter([], "sync")).toBeNull()
  })
})

describe("filterMembersByQuotePlan", () => {
  const members = [
    { code: "000001", quote_plan: "full" as const, needs_sync: true },
    { code: "600887", quote_plan: "fill" as const, needs_sync: true },
    { code: "600519", quote_plan: "current" as const, needs_sync: false },
  ]

  it("全部不过滤", () => {
    expect(filterMembersByQuotePlan(members, "all")).toEqual(members)
  })

  it("需同步包含全历史和补缺口", () => {
    expect(filterMembersByQuotePlan(members, "sync")).toEqual([
      members[0],
      members[1],
    ])
  })

  it("没有标记的成员进不了需同步", () => {
    expect(
      filterMembersByQuotePlan([{ code: "000002", quote_plan: undefined }], "sync")
    ).toEqual([])
  })
})

describe("memberNeedsSync", () => {
  it("优先用 needs_sync，否则回退 quote_plan", () => {
    expect(memberNeedsSync({ needs_sync: true, quote_plan: "current" })).toBe(true)
    expect(memberNeedsSync({ quote_plan: "fill" })).toBe(true)
    expect(memberNeedsSync({ quote_plan: "current" })).toBe(false)
  })
})

describe("isQuoteFilter", () => {
  it("只接受全部和需同步", () => {
    expect(isQuoteFilter("sync")).toBe(true)
    expect(isQuoteFilter("fill")).toBe(false)
  })
})
