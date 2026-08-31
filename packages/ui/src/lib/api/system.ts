import { apiUrl, apiUrlWithQuery, requestJson } from "./http"

export type Status = {
  db: string
  pool: string
  trade_date?: string | null
  need_sync: number
  need_full?: number
  need_fill?: number
  already_current?: number
  profile_filled: number
  pool_active: number
  pool_removed: number
  stocks: number
  bars_daily: number
  bars_weekly?: number
  bars_monthly?: number
}

export async function getHealth(): Promise<boolean> {
  try {
    const body = await requestJson<unknown>(apiUrl("/api/health"))
    return typeof body === "object" && body !== null && "ok" in body && (body as { ok: unknown }).ok === true
  } catch {
    return false
  }
}

export function queryStatus(pool?: string): Promise<Status> {
  return requestJson<Status>(apiUrlWithQuery("/api/status", { pool }))
}
