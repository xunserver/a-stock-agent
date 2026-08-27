import type { Job, JobStatus } from "@/lib/api"
import { normalizeStockCode } from "@/lib/ticker"

export const SUCCESS_VISIBILITY_MS = 5000
export const TRACKER_JOB_LIMIT = 5

export function isOpenJob(status: JobStatus) {
  return status === "queued" || status === "running"
}

export function jobStatusLabel(status: JobStatus) {
  if (status === "queued") return "排队"
  if (status === "running") return "运行中"
  if (status === "succeeded") return "成功"
  if (status === "cancelled") return "已取消"
  return "失败"
}

export function jobStatusVariant(
  status: JobStatus
): "outline" | "secondary" | "default" | "destructive" {
  if (status === "queued") return "outline"
  if (status === "running") return "secondary"
  if (status === "succeeded") return "default"
  if (status === "cancelled") return "outline"
  return "destructive"
}

export function jobTypeLabel(type: string) {
  if (type === "quotes.sync") return "同步行情"
  if (type === "stock.sync") return "同步股票资料与行情"
  if (type === "boards.sync") return "同步板块"
  if (type === "analyze.run") return "运行股票分析"
  if (type === "stock.add") return "加入股票"
  if (type === "stock.remove") return "移除股票"
  if (type === "pool.add") return "添加股票池成员"
  if (type === "pool.set") return "覆盖股票池成员"
  if (type === "pool.remove") return "移出股票池成员"
  if (type === "pool.create") return "创建股票池"
  if (type === "pool.delete") return "删除股票池"
  if (type === "settings.update") return "更新设置"
  return type
}

export function jobDisplayName(job: Job) {
  const name = job.name?.trim()
  if (name) return name
  return jobTypeLabel(job.type)
}

const PARAM_LABELS: Record<string, string> = {
  pool: "股票池",
  codes: "代码",
  code: "代码",
  ticker: "代码（行情）",
  index: "指数",
  adjust: "复权",
  sleep: "请求间隔（秒）",
  limit: "数量上限",
  kind: "板块类型",
  date: "日期",
  analysts: "分析师",
  module: "模块",
  section: "分区",
  name: "名称",
  settings: "设置",
  values: "取值",
}

const BOARD_KIND_LABELS: Record<string, string> = {
  all: "全部",
  industry: "行业",
  concept: "概念",
}

export type JobParamRow = { label: string; value: string }

function formatParamValue(key: string, value: unknown): string | null {
  if (value == null) return null
  if (key === "kind" && typeof value === "string") {
    return BOARD_KIND_LABELS[value] ?? value
  }
  if (Array.isArray(value)) {
    const parts = value.map((item) => String(item)).filter(Boolean)
    return parts.length > 0 ? parts.join(", ") : null
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  const text = String(value).trim()
  return text || null
}

export function describeJobParams(
  command: Record<string, unknown>
): JobParamRow[] {
  const rows: JobParamRow[] = []
  for (const [key, value] of Object.entries(command)) {
    if (key === "type") continue
    const formatted = formatParamValue(key, value)
    if (formatted == null) continue
    rows.push({
      label: PARAM_LABELS[key] ?? key,
      value: formatted,
    })
  }
  return rows
}

export function formatTimeoutSeconds(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—"
  if (seconds < 60) return `${seconds} 秒`
  if (seconds % 3600 === 0) return `${seconds / 3600} 小时`
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`
  return `${seconds} 秒`
}

export function formatJobDateTime(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

export function summarizeJobError(error: string | null) {
  if (!error) return "—"
  const text = error.replace(/\s+/g, " ").trim()
  return text.length <= 48 ? text : `${text.slice(0, 48)}…`
}

export function countJobsAhead(jobs: Job[], job: Job) {
  return jobs.filter(
    (item) =>
      item.id !== job.id &&
      isOpenJob(item.status) &&
      item.created_at <= job.created_at
  ).length
}

export function jobQueuedHint(jobs: Job[], job: Job) {
  if (job.status !== "queued") return null
  const ahead = countJobsAhead(jobs, job)
  if (ahead <= 0) return null
  return `前面还有 ${ahead} 个任务`
}

export function withQueuedHint(message: string, jobs: Job[], job: Job) {
  const hint = jobQueuedHint(jobs, job)
  return hint ? `${message}，${hint}` : message
}

export function trackerJobDetail(jobs: Job[], job: Job) {
  if (job.status === "running" && job.log_count > 0) {
    return `已产生 ${job.log_count} 行日志`
  }
  const queued = jobQueuedHint(jobs, job)
  if (queued) return queued
  return `${job.id} · ${jobStatusLabel(job.status)}`
}

export function selectTrackerJobs(
  jobs: Job[],
  dismissed: ReadonlySet<string>,
  now = Date.now()
) {
  const priority: Record<JobStatus, number> = {
    running: 0,
    queued: 1,
    failed: 2,
    succeeded: 3,
    cancelled: 4,
  }
  return jobs
    .filter((job) => {
      if (!job.background || dismissed.has(job.id)) return false
      if (job.status === "cancelled") return false
      if (isOpenJob(job.status) || job.status === "failed") return true
      if (job.status !== "succeeded" || !job.finished_at) return false
      const finishedAt = new Date(job.finished_at).getTime()
      return (
        Number.isFinite(finishedAt) && now - finishedAt < SUCCESS_VISIBILITY_MS
      )
    })
    .sort(
      (a, b) =>
        priority[a.status] - priority[b.status] ||
        b.created_at.localeCompare(a.created_at)
    )
}

export function shouldPollJobs(
  jobs: Job[],
  dismissed: ReadonlySet<string>,
  forced: boolean
) {
  if (forced) return true
  return jobs.some(
    (job) =>
      job.background &&
      (isOpenJob(job.status) ||
        (job.status === "failed" && !dismissed.has(job.id)))
  )
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function readString(
  source: Record<string, unknown>,
  key: string
): string | null {
  const value = source[key]
  return typeof value === "string" && value.trim() ? value : null
}

export function pickJobString(job: Job, key: string): string | null {
  return readString(asRecord(job.result), key) ?? readString(job.command, key)
}

export function analyzeJobHref(job: Job): string | null {
  if (job.type !== "analyze.run" || job.status !== "succeeded") return null
  const code = pickJobString(job, "code")
  const date = pickJobString(job, "date")
  const run = pickJobString(job, "run_id")
  if (!code || !date) return null
  const params = new URLSearchParams({ code, date })
  if (run) params.set("run", run)
  return `/analyze?${params.toString()}`
}

export function pickJobCodes(job: Job): string[] {
  const result = asRecord(job.result)
  const found: string[] = []
  const single = readString(result, "code") ?? readString(job.command, "code")
  if (single) found.push(single)
  if (Array.isArray(job.command.codes)) {
    for (const item of job.command.codes) {
      if (typeof item === "string" && item.trim()) found.push(item)
    }
  }
  return [...new Set(found.map(normalizeStockCode).filter(Boolean))].slice(0, 8)
}
