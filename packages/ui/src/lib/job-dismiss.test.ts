import { beforeEach, describe, expect, it } from "vitest"

import { readDismissedJobs, writeDismissedJobs } from "@/lib/job-dismiss"

describe("job dismiss storage", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("在当前会话保存和恢复任务 id", () => {
    writeDismissedJobs(new Set(["a", "b"]))
    expect(readDismissedJobs()).toEqual(new Set(["a", "b"]))
  })

  it("损坏的数据会安全回退为空集合", () => {
    window.sessionStorage.setItem("astock.job-dismissed", "{")
    expect(readDismissedJobs()).toEqual(new Set())
  })
})
