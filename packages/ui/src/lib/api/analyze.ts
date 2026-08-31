import { apiUrlWithQuery, requestJson } from "./http"
import { submitCommand, type Job } from "./jobs"
import type { AnalystKind } from "./settings"

export type AnalyzeReportSummary = {
  code: string
  ticker?: string
  name?: string | null
  date: string
  run_id: string
  decision?: string | null
  created_at?: string
  report_dir?: string
}
export type AnalyzeReportList = { count: number; reports: AnalyzeReportSummary[] }
export type AnalyzeReportDetail = AnalyzeReportSummary & {
  meta?: AnalyzeReportSummary
  complete_report?: string | null
  sections?: Record<string, string | null | undefined>
}

export function submitAnalyzeRun(input: {
  pool: string
  code: string
  date: string
  analysts: AnalystKind[]
}): Promise<Job> {
  return submitCommand({ type: "analyze.run", ...input })
}

export async function listAnalyzeReports(input?: { pool?: string; code?: string }): Promise<AnalyzeReportList> {
  const body = await requestJson<Partial<AnalyzeReportList>>(
    apiUrlWithQuery("/api/analyses", { code: input?.code })
  )
  const reports = Array.isArray(body.reports) ? body.reports : []
  return { count: body.count ?? reports.length, reports }
}

export async function getAnalyzeReport(input: {
  code: string
  date: string
  run_id?: string
}): Promise<AnalyzeReportDetail> {
  const raw = await requestJson<AnalyzeReportDetail>(apiUrlWithQuery(
    `/api/analyses/${encodeURIComponent(input.code)}/${encodeURIComponent(input.date)}`,
    { run_id: input.run_id }
  ))
  const meta = raw.meta
  return {
    ...raw,
    code: raw.code || meta?.code || input.code,
    date: raw.date || meta?.date || input.date,
    run_id: raw.run_id || meta?.run_id || input.run_id || "",
    name: raw.name ?? meta?.name,
    decision: raw.decision ?? meta?.decision,
    created_at: raw.created_at ?? meta?.created_at,
    complete_report: raw.complete_report ?? null,
    sections: raw.sections,
    meta,
  }
}
