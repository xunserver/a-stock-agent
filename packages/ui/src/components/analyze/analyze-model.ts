import type { AnalystKind, AnalyzeReportDetail, Job } from "@/lib/api"
import { isOpenJob } from "@/lib/jobs"

export const ANALYST_OPTIONS: { id: AnalystKind; label: string }[] = [
  { id: "market", label: "技术" },
  { id: "news", label: "新闻" },
  { id: "fundamentals", label: "基本面" },
  { id: "social", label: "情绪" },
]

export const REPORT_SECTIONS = [
  { id: "summary", label: "摘要" },
  { id: "market", label: "技术" },
  { id: "news", label: "新闻" },
  { id: "fundamentals", label: "基本面" },
  { id: "research", label: "研究" },
  { id: "trading", label: "交易" },
  { id: "risk", label: "风险" },
  { id: "portfolio", label: "组合" },
  { id: "full", label: "全文" },
] as const

export type ReportSectionId = (typeof REPORT_SECTIONS)[number]["id"]

export function isAnalyst(value: string): value is AnalystKind {
  return ANALYST_OPTIONS.some((item) => item.id === value)
}

export function pickOpenAnalyzeJob(jobs: Job[]): Job | null {
  const open = jobs.filter(
    (job) => job.type === "analyze.run" && isOpenJob(job.status)
  )
  return (
    open.find((job) => job.status === "running") ??
    [...open].sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ??
    null
  )
}

export function reportSectionText(
  report: AnalyzeReportDetail,
  section: ReportSectionId
): string {
  if (section === "full") {
    return (
      collectMarkdown(report, ["complete_report"]) ||
      (typeof report.complete_report === "string" ? report.complete_report : "")
    )
  }
  if (section === "summary") {
    const decision = report.decision || report.meta?.decision || ""
    const summary = collectMarkdown(report, ["summary"])
    return [decision ? `决策：${decision}` : "", summary]
      .filter(Boolean)
      .join("\n\n")
  }
  if (section === "research")
    return collectMarkdown(report, ["research", "bull", "bear", "manager"])
  if (section === "trading")
    return collectMarkdown(report, ["trading", "trader"])
  if (section === "risk")
    return collectMarkdown(report, [
      "risk",
      "aggressive",
      "conservative",
      "neutral",
    ])
  if (section === "portfolio")
    return collectMarkdown(report, ["portfolio", "decision.md", "5_portfolio"])
  return collectMarkdown(report, [section])
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function collectMarkdown(report: AnalyzeReportDetail, keys: string[]): string {
  const root = asRecord(report)
  const meta = asRecord(report.meta)
  const sections = asRecord(report.sections)
  const bags = [sections, root, meta]
  for (const nested of [
    "analysts",
    "research",
    "trading",
    "risk",
    "portfolio",
    "1_analysts",
    "2_research",
    "3_trading",
    "4_risk",
    "5_portfolio",
  ]) {
    bags.push(
      asRecord(root[nested]),
      asRecord(sections[nested]),
      asRecord(meta[nested])
    )
  }
  return keys
    .map((key) => {
      for (const alias of [key, `${key}.md`]) {
        for (const bag of bags) {
          const value = bag[alias]
          if (typeof value === "string" && value.trim()) return value
        }
      }
      return ""
    })
    .filter(Boolean)
    .join("\n\n")
}
