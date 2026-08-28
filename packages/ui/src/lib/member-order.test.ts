import { describe, expect, it } from "vitest"

import {
  activeMemberCodes,
  moveMemberDown,
  moveMemberToFirst,
  moveMemberUp,
} from "./member-order"

describe("activeMemberCodes", () => {
  it("只保留 active 并保持原顺序", () => {
    expect(
      activeMemberCodes([
        { code: "600519", status: "active" },
        { code: "000001", status: "removed" },
        { code: "000002", status: "active" },
      ])
    ).toEqual(["600519", "000002"])
  })
})

describe("moveMemberUp", () => {
  it("未筛选时与上一只互换", () => {
    expect(moveMemberUp(["a", "b", "c"], ["a", "b", "c"], "c")).toEqual([
      "a",
      "c",
      "b",
    ])
  })

  it("筛选时插到上一只可见成员之前", () => {
    expect(moveMemberUp(["a", "b", "c"], ["a", "c"], "c")).toEqual([
      "c",
      "a",
      "b",
    ])
  })

  it("已是可见列表第一只则不动", () => {
    expect(moveMemberUp(["a", "b", "c"], ["a", "c"], "a")).toBeNull()
  })
})

describe("moveMemberDown", () => {
  it("未筛选时与下一只互换", () => {
    expect(moveMemberDown(["a", "b", "c"], ["a", "b", "c"], "a")).toEqual([
      "b",
      "a",
      "c",
    ])
  })

  it("筛选时插到下一只可见成员之后", () => {
    expect(moveMemberDown(["a", "b", "c"], ["a", "c"], "a")).toEqual([
      "b",
      "c",
      "a",
    ])
  })
})

describe("moveMemberToFirst", () => {
  it("未筛选时挪到列表第一位，不钉死在顶部", () => {
    expect(moveMemberToFirst(["a", "b", "c"], ["a", "b", "c"], "c")).toEqual([
      "c",
      "a",
      "b",
    ])
  })

  it("筛选时挪到当前可见列表第一位", () => {
    expect(moveMemberToFirst(["a", "b", "c"], ["b", "c"], "c")).toEqual([
      "a",
      "c",
      "b",
    ])
  })

  it("已是可见列表第一只则不动", () => {
    expect(moveMemberToFirst(["a", "b", "c"], ["b", "c"], "b")).toBeNull()
  })
})
