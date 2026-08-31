import { apiUrl, apiUrlWithQuery, requestJson } from "./http"
import type { Job, JobStatus } from "./jobs"

export type ScheduleKind = "daily" | "weekly" | "trading_day"
export type Automation = {
  id: string
  name: string
  description: string
  command: Record<string, unknown>
  schedule_kind: ScheduleKind
  local_time: string
  timezone: string
  weekdays: number[]
  enabled: boolean
  archived: boolean
  misfire_policy: "run_once" | "skip"
  next_run_at: string | null
  last_run_at: string | null
  calendar_status: string | null
  created_at: string
  updated_at: string
  last_status: JobStatus | null
  last_job_id: string | null
  last_finished_at: string | null
}
export type AutomationInput = {
  name: string
  description?: string
  command: Record<string, unknown>
  schedule_kind: ScheduleKind
  local_time: string
  timezone: string
  weekdays?: number[]
  enabled: boolean
  misfire_policy?: "run_once" | "skip"
}
export type AutomationCommandField = {
  name: string
  label: string
  kind: "text" | "select"
  default?: string
  optional?: boolean
  options?: { value: string; label: string }[]
}
export type AutomationCommandDefinition = {
  type: string
  label: string
  description: string
  fields: AutomationCommandField[]
}

export async function listAutomations(): Promise<Automation[]> {
  const body = await requestJson<{ automations?: Automation[] }>(apiUrl("/api/automations"))
  return Array.isArray(body.automations) ? body.automations : []
}
export function getAutomation(id: string): Promise<Automation> {
  return requestJson<Automation>(apiUrl(`/api/automations/${id}`))
}
export async function getAutomationCatalog(): Promise<AutomationCommandDefinition[]> {
  const body = await requestJson<{ commands?: AutomationCommandDefinition[] }>(apiUrl("/api/automations/catalog"))
  return Array.isArray(body.commands) ? body.commands : []
}
export function createAutomation(input: AutomationInput): Promise<Automation> {
  return requestJson<Automation>(apiUrl("/api/automations"), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
  })
}
export function updateAutomation(id: string, input: Partial<AutomationInput>): Promise<Automation> {
  return requestJson<Automation>(apiUrl(`/api/automations/${id}`), {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
  })
}
export function archiveAutomation(id: string): Promise<Automation> {
  return requestJson<Automation>(apiUrl(`/api/automations/${id}`), { method: "DELETE" })
}
export function runAutomation(id: string): Promise<Job> {
  return requestJson<Job>(apiUrl(`/api/automations/${id}/run`), { method: "POST" })
}
export async function listAutomationRuns(id: string, date?: string): Promise<{ jobs: Job[]; count: number }> {
  const body = await requestJson<{ jobs?: Job[]; count?: number }>(apiUrlWithQuery(
    `/api/automations/${id}/runs`, { date }
  ))
  const jobs = Array.isArray(body.jobs) ? body.jobs : []
  return { jobs, count: body.count ?? jobs.length }
}
