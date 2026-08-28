import { describe, expect, it } from "vitest"

import { filterMembersByQuery, memberMatchesQuery } from "@/lib/member-query"

const members = [
  { code: "000001", name: "平安银行" },
  { code: "600519", name: "贵州茅台" },
  { code: "300750", name: "宁德时代" },
]

describe("memberMatchesQuery", () => {
  it("空查询匹配全部", () => {
    expect(memberMatchesQuery(members[0], "  ")).toBe(true)
  })

  it("按代码或带交易所后缀模糊匹配", () => {
    expect(memberMatchesQuery(members[0], "000")).toBe(true)
    expect(memberMatchesQuery(members[0], "000001.SZ")).toBe(true)
    expect(memberMatchesQuery(members[1], "600519.ss")).toBe(true)
    expect(memberMatchesQuery(members[0], "600")).toBe(false)
  })

  it("按名称模糊匹配，忽略大小写和空白", () => {
    expect(memberMatchesQuery(members[1], "茅台")).toBe(true)
    expect(memberMatchesQuery(members[1], "贵州 茅")).toBe(true)
    expect(memberMatchesQuery(members[2], "宁德")).toBe(true)
    expect(memberMatchesQuery(members[2], "茅台")).toBe(false)
  })
})

describe("filterMembersByQuery", () => {
  it("空查询不过滤", () => {
    expect(filterMembersByQuery(members, "")).toEqual(members)
  })

  it("按代码或名称缩小列表", () => {
    expect(filterMembersByQuery(members, "300")).toEqual([members[2]])
    expect(filterMembersByQuery(members, "银行")).toEqual([members[0]])
  })

  it("没有成员时保持空", () => {
    expect(filterMembersByQuery(null, "茅台")).toBeNull()
  })
})
