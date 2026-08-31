import { apiUrl, apiUrlWithQuery, isJsonObject, requestJson } from "./http"

export type JobStatus =
  "queued" | "running" | "succeeded" | "failed" | "cancelled"

export type Job = {
  id: string
  type: string
  name: string
  status: JobStatus
  command: Record<string, unknown>
  background: boolean
  timeout_seconds: number
  trigger?: "manual" | "scheduled" | "automation_manual"
  automation_id?: string | null
  scheduled_for?: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  result: Record<string, unknown> | null
  error: string | null
  log_count: number
  log?: string[]
}

export async function submitCommand(
  payload: Record<string, unknown>
): Promise<Job> {
  const body = await requestJson<unknown>(apiUrl("/api/jobs"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return parseJob(body)
}

export async function listJobs(filters?: {
  automation_id?: string
  date?: string
  trigger?: string
  limit?: number
  offset?: number
}): Promise<Job[]> {
  const body = await requestJson<unknown>(
    apiUrlWithQuery("/api/jobs", filters ?? {})
  )
  if (!isJsonObject(body) || !Array.isArray(body.jobs)) return []
  return body.jobs.map(parseJob)
}

export async function getJob(jobId: string): Promise<Job> {
  return parseJob(await requestJson<unknown>(apiUrl(`/api/jobs/${jobId}`)))
}

export async function cancelJob(jobId: string): Promise<Job> {
  const body = await requestJson<unknown>(apiUrl(`/api/jobs/${jobId}/cancel`), {
    method: "POST",
  })
  return parseJob(body)
}

export async function waitForJob(job: Job): Promise<Job> {
  if (job.status === "succeeded") return job
  if (job.status === "failed") throw new Error(job.error || "任务失败")
  return new Promise((resolve, reject) => {
    watchJob(
      job.id,
      () => undefined,
      (done) => {
        if (done.status === "failed") {
          reject(new Error(done.error || "任务失败"))
          return
        }
        resolve(done)
      },
      reject
    )
  })
}

/** SSE remains separate from requestJson because it is a long-lived event stream. */
export function watchJob(
  jobId: string,
  onLog: (line: string) => void,
  onDone: (job: Job) => void,
  onError: (message: string) => void
): () => void {
  const source = new EventSource(apiUrl(`/api/jobs/${jobId}/events`))
  let settled = false
  source.onmessage = (event) => {
    let payload: unknown
    try {
      payload = JSON.parse(event.data)
    } catch {
      return
    }
    if (!isJsonObject(payload)) return
    const stream = payload.stream
    if (
      stream === "log" &&
      "message" in payload &&
      typeof payload.message === "string"
    ) {
      onLog(payload.message)
      return
    }
    if (stream === "status") {
      settled = true
      source.close()
      try {
        onDone(parseJob(payload.data))
        return
      } catch {
        onError("任务结束，但没有返回有效结果")
      }
    }
  }
  source.onerror = () => {
    if (settled) return
    settled = true
    source.close()
    onError("与 core 的任务流断开")
  }
  return () => {
    settled = true
    source.close()
  }
}

const JOB_STATUSES: ReadonlySet<string> = new Set([
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
])

function isJobStatus(value: unknown): value is JobStatus {
  return typeof value === "string" && JOB_STATUSES.has(value)
}

/** Validate the live/persisted Job contract at the HTTP and SSE boundary. */
function parseJob(value: unknown): Job {
  if (
    !isJsonObject(value) ||
    typeof value.id !== "string" ||
    typeof value.type !== "string" ||
    typeof value.name !== "string" ||
    !isJobStatus(value.status) ||
    !isJsonObject(value.command) ||
    typeof value.background !== "boolean" ||
    typeof value.timeout_seconds !== "number" ||
    typeof value.created_at !== "string" ||
    typeof value.log_count !== "number"
  ) {
    throw new Error("core 返回了无效的任务数据")
  }
  return {
    id: value.id,
    type: value.type,
    name: value.name,
    status: value.status,
    command: value.command,
    background: value.background,
    timeout_seconds: value.timeout_seconds,
    trigger:
      value.trigger === "scheduled" || value.trigger === "automation_manual"
        ? value.trigger
        : "manual",
    automation_id:
      typeof value.automation_id === "string" ? value.automation_id : null,
    scheduled_for:
      typeof value.scheduled_for === "string" ? value.scheduled_for : null,
    created_at: value.created_at,
    started_at: typeof value.started_at === "string" ? value.started_at : null,
    finished_at:
      typeof value.finished_at === "string" ? value.finished_at : null,
    result: isJsonObject(value.result) ? value.result : null,
    error: typeof value.error === "string" ? value.error : null,
    log_count: value.log_count,
    ...(Array.isArray(value.log) &&
    value.log.every((line) => typeof line === "string")
      ? { log: value.log }
      : {}),
  }
}
