import { apiUrl, apiUrlWithQuery, requestJson } from "./http"
import { submitCommand, waitForJob, type Job } from "./jobs"

export type QuotePlan = "full" | "fill" | "current"

export type PoolMember = {
  code: string
  name: string | null
  status: string
  source: string | null
  last_bar: string | null
  quote_plan?: QuotePlan | null
  needs_sync?: boolean | null
  sort_order?: number | null
}

export type PoolList = { pool: string; count: number; members: PoolMember[] }

export type PoolSummary = {
  id: string
  name: string
  created_at: string
  active: number
  removed: number
}

export type PoolsList = { count: number; pools: PoolSummary[] }

export function queryPools(): Promise<PoolsList> {
  return requestJson<PoolsList>(apiUrl("/api/pools"))
}

export function queryPoolList(
  pool?: string,
  includeRemoved = false
): Promise<PoolList> {
  return requestJson<PoolList>(
    apiUrlWithQuery(
      `/api/pools/${encodeURIComponent(pool ?? "default")}/members`,
      { include_removed: includeRemoved }
    )
  )
}

export function submitQuotesSync(
  pool = "default",
  codes?: string[]
): Promise<Job> {
  return submitCommand({
    type: "quotes.sync",
    pool,
    ...(codes && codes.length > 0 ? { codes } : {}),
  })
}

export async function createPool(id: string, name: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.create", pool: id, name }))
}

export async function deletePool(id: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.delete", pool: id }))
}

export async function addPoolCodes(pool: string, codes: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.add", pool, codes }))
}

export function addPoolIndex(
  pool: string,
  index: string,
  replace = false
): Promise<Job> {
  return submitCommand({
    type: replace ? "pool.set" : "pool.add",
    pool,
    index,
    background: true,
  })
}

export async function removePoolCodes(pool: string, codes: string[]): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.remove", pool, codes }))
}

export async function reorderPoolMembers(pool: string, codes: string[]): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.reorder", pool, codes }))
}
