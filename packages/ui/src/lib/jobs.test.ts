import { describe, expect, it } from "vitest"

import type { Job, JobStatus } from "@/lib/api"
import {
  describeJobParams,
  formatTimeoutSeconds,
  jobDisplayName,
  jobQueuedHint,
  jobStatusLabel,
  selectTrackerJobs,
  shouldPollJobs,
  trackerJobDetail,
  SUCCESS_VISIBILITY_MS,
  TRACKER_JOB_LIMIT,
} from "@/lib/jobs"

function job(id: string, status: JobStatus, options: Partial<Job> = {}): Job {
  return {
    id,
    type: "quotes.sync",
    name: "同步行情 · 全部（池 default）",
    status,
    command: { type: "quotes.sync" },
    background: true,
    timeout_seconds: 7200,
    created_at: `2026-08-27T10:00:${id.padStart(2, "0")}Z`,
    started_at: null,
    finished_at: null,
    result: null,
    error: null,
    log_count: 0,
    ...options,
  }
}

describe("selectTrackerJobs", () => {
  it("仅返回 background 可见任务并按状态优先级排序", () => {
    const now = Date.parse("2026-08-27T10:01:00Z")
    const jobs = [
      job("1", "failed"),
      job("2", "queued"),
      job("3", "running"),
      job("4", "succeeded", {
        finished_at: new Date(now - 1000).toISOString(),
      }),
      job("5", "running", { background: false }),
    ]
    expect(
      selectTrackerJobs(jobs, new Set(), now).map((item) => item.id)
    ).toEqual(["3", "2", "1", "4"])
  })

  it("成功任务只在五秒窗口内可见，失败可被关闭", () => {
    const now = Date.parse("2026-08-27T10:01:00Z")
    const recent = job("1", "succeeded", {
      finished_at: new Date(now - SUCCESS_VISIBILITY_MS + 1).toISOString(),
    })
    const old = job("2", "succeeded", {
      finished_at: new Date(now - SUCCESS_VISIBILITY_MS).toISOString(),
    })
    const failed = job("3", "failed")
    expect(
      selectTrackerJobs([recent, old, failed], new Set(["3"]), now)
    ).toEqual([recent])
  })

  it("选择器保留全部可见任务，由组件按上限截取", () => {
    const selected = selectTrackerJobs(
      Array.from({ length: TRACKER_JOB_LIMIT + 2 }, (_, index) =>
        job(String(index), "queued")
      ),
      new Set()
    )
    expect(selected).toHaveLength(TRACKER_JOB_LIMIT + 2)
    expect(selected.slice(0, TRACKER_JOB_LIMIT)).toHaveLength(TRACKER_JOB_LIMIT)
  })

  it("已取消的任务立刻从浮层消失", () => {
    expect(
      selectTrackerJobs([job("1", "cancelled")], new Set()).map(
        (item) => item.id
      )
    ).toEqual([])
  })
})

describe("shouldPollJobs", () => {
  it("活跃后台任务、未关闭失败任务和 forced 模式会轮询", () => {
    expect(shouldPollJobs([job("1", "running")], new Set(), false)).toBe(true)
    expect(shouldPollJobs([job("2", "failed")], new Set(), false)).toBe(true)
    expect(shouldPollJobs([job("2", "failed")], new Set(["2"]), false)).toBe(
      false
    )
    expect(shouldPollJobs([], new Set(), true)).toBe(true)
    expect(shouldPollJobs([job("3", "cancelled")], new Set(), false)).toBe(
      false
    )
  })
})

describe("job status and queue hints", () => {
  it("cancelled 显示为已取消", () => {
    expect(jobStatusLabel("cancelled")).toBe("已取消")
  })

  it("排队中的任务能算出前面还有几个", () => {
    const running = job("1", "running")
    const queued = job("2", "queued")
    expect(jobQueuedHint([running, queued], queued)).toBe("前面还有 1 个任务")
    expect(jobQueuedHint([running, queued], running)).toBeNull()
    expect(
      trackerJobDetail([running], job("3", "running", { log_count: 4 }))
    ).toBe("已产生 4 行日志")
  })
})

describe("jobDisplayName and describeJobParams", () => {
  it("优先使用服务端 name", () => {
    expect(
      jobDisplayName(
        job("1", "queued", { name: "同步行情 · 600519", type: "quotes.sync" })
      )
    ).toBe("同步行情 · 600519")
    expect(
      jobDisplayName(job("2", "queued", { name: "", type: "analyze.run" }))
    ).toBe("运行 AI 分析")
  })

  it("用中文标签描述提交参数", () => {
    expect(
      describeJobParams({
        type: "quotes.sync",
        pool: "hs",
        codes: ["600519", "000001"],
        adjust: "qfq",
      })
    ).toEqual([
      { label: "股票池", value: "hs" },
      { label: "代码", value: "600519, 000001" },
      { label: "复权", value: "qfq" },
    ])
    expect(formatTimeoutSeconds(7200)).toBe("2 小时")
    expect(formatTimeoutSeconds(90)).toBe("90 秒")
  })
})
