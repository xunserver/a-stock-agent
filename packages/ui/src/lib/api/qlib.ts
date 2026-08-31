import { apiUrl, apiUrlWithQuery, requestJson } from "./http"
import { submitCommand, waitForJob, type Job } from "./jobs"
import type { PoolSummary } from "./pools"

export type QlibWorkflow = {
  config: string
  benchmark: string
  topk: number
  n_drop: number
  account: number
  data_end?: string | null
  test_start?: string | null
  learning_rate?: number | null
  pool?: string
  updated_at?: string | null
}

export type QlibCandidate = {
  rank: number
  code: string
  symbol: string
  name: string
  score: number
  next_day_pct_chg?: number | null
}

export type QlibRun = {
  id: string
  run_id: string
  job_id: string
  pool: string
  as_of: string
  workflow: QlibWorkflow
  artifact_ref: string
  universe_size: number
  candidate_count: number
  created_at: string
  next_trade_date?: string | null
  candidates?: QlibCandidate[]
}

export type QlibOverview = {
  pool: PoolSummary
  workflow: QlibWorkflow
  data: {
    ready: boolean
    qlib_dir: string
    calendar_first: string | null
    calendar_last: string | null
    pool_members: number
    symbol_count: number
    prepared_at: string | null
  }
  latest_run: QlibRun | null
}

export function queryQlibOverview(pool: string): Promise<QlibOverview> {
  return requestJson<QlibOverview>(apiUrlWithQuery("/api/qlib/overview", { pool }))
}

export async function listQlibRuns(pool: string): Promise<QlibRun[]> {
  const body = await requestJson<{ runs: QlibRun[] }>(
    apiUrlWithQuery("/api/qlib/runs", { pool })
  )
  return body.runs
}

export function getQlibRun(runId: string): Promise<QlibRun> {
  return requestJson<QlibRun>(apiUrl(`/api/qlib/runs/${encodeURIComponent(runId)}`))
}

export function submitQlibRun(pool: string, workflow: QlibWorkflow): Promise<Job> {
  return submitCommand({ type: "qlib.run", pool, workflow, background: true })
}

export function submitQlibDump(pool: string): Promise<Job> {
  return submitCommand({ type: "qlib.dump", pool, background: true })
}

export async function saveQlibWorkflow(pool: string, workflow: QlibWorkflow): Promise<Job> {
  return waitForJob(await submitCommand({ type: "qlib.workflow.update", pool, workflow }))
}
