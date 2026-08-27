export type Status = {
  db: string
  pool: string
  need_full: number
  need_fill: number
  already_current: number
  profile_filled: number
  pool_active: number
  pool_removed: number
  stocks: number
  bars_daily: number
}

export type PoolMember = {
  code: string
  name: string | null
  status: string
  source: string | null
  last_bar: string | null
}

export type PoolList = {
  pool: string
  count: number
  members: PoolMember[]
}

export type PoolSummary = {
  id: string
  name: string
  created_at: string
  active: number
  removed: number
}

export type PoolsList = {
  count: number
  pools: PoolSummary[]
}

const API_BASE = import.meta.env.VITE_API_BASE ?? ""

function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

export async function queryPools(): Promise<PoolsList> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "pools.list" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as PoolsList
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed"

export type Job = {
  id: string
  type: string
  status: JobStatus
  command: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
  result: Record<string, unknown> | null
  error: string | null
  log_count: number
  log?: string[]
}

type ErrorBody = {
  error?: unknown
  detail?: unknown
}

async function readError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null)
  if (typeof body === "object" && body !== null) {
    const payload = body as ErrorBody
    if (typeof payload.error === "string") {
      return payload.error
    }
    if (typeof payload.detail === "string") {
      return payload.detail
    }
  }
  return `HTTP ${response.status}`
}

export async function getHealth(): Promise<boolean> {
  try {
    const response = await fetch(apiUrl("/api/health"))
    if (!response.ok) {
      return false
    }
    const body: unknown = await response.json()
    return (
      typeof body === "object" &&
      body !== null &&
      "ok" in body &&
      (body as { ok: unknown }).ok === true
    )
  } catch {
    return false
  }
}

export async function queryStatus(pool?: string): Promise<Status> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "status", ...(pool ? { pool } : {}) }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as Status
}

export async function queryPoolList(
  pool?: string,
  includeRemoved = false
): Promise<PoolList> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "pool.list",
      ...(pool ? { pool } : {}),
      include_removed: includeRemoved,
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as PoolList
}

export type StockPoolRef = {
  id: string
  name: string
}

export type StockRow = {
  code: string
  name: string | null
  industry: string | null
  is_st: number
  is_suspended: number
  last_bar: string | null
  pools: StockPoolRef[]
}

export type StocksList = {
  count: number
  in_pool: number
  profile_filled: number
  stocks: StockRow[]
}

export async function queryStocks(): Promise<StocksList> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "stocks.list" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as StocksList
}

export type LlmProvider =
  | "openai_compatible"
  | "qwen-cn"
  | "deepseek"
  | "glm-cn"
  | "ollama"
  | "openai"

export type OutputLanguage = "Chinese" | "English"

export type AnalystKind = "market" | "social" | "news" | "fundamentals"

export type AnalyzeSettings = {
  llm_provider: LlmProvider
  deep_think_llm: string
  quick_think_llm: string
  backend_url: string
  api_key_set: boolean
  api_key_hint: string
  output_language: OutputLanguage
  analysts: AnalystKind[]
  max_debate_rounds: number
  max_risk_discuss_rounds: number
  temperature: number | null
  checkpoint_enabled: boolean
}

export type AnalyzeSettingsPatch = Partial<
  Omit<AnalyzeSettings, "api_key_set" | "api_key_hint">
> & {
  api_key?: string
}

export const DEFAULT_ANALYZE_SETTINGS: AnalyzeSettings = {
  llm_provider: "openai_compatible",
  deep_think_llm: "",
  quick_think_llm: "",
  backend_url: "",
  api_key_set: false,
  api_key_hint: "",
  output_language: "Chinese",
  analysts: ["market", "news", "fundamentals"],
  max_debate_rounds: 1,
  max_risk_discuss_rounds: 1,
  temperature: null,
  checkpoint_enabled: false,
}

export type Settings = {
  pool: string
  adjust: "" | "qfq" | "hfq"
  quotes: {
    sync_enabled: boolean
    sync_time: string
    timezone: string
    sleep: number
  }
  analyze: AnalyzeSettings
  paths: {
    data: string
    db: string
    qlib: string
    config: string
    analyze: string
    system?: string
  }
}

export type SettingsPatch = {
  pool?: string
  adjust?: "" | "qfq" | "hfq"
  quotes?: Partial<Settings["quotes"]>
  analyze?: AnalyzeSettingsPatch
}

function normalizeAnalyzeSettings(raw: unknown): AnalyzeSettings {
  const value =
    typeof raw === "object" && raw !== null
      ? (raw as Partial<AnalyzeSettings>)
      : {}
  const analysts = Array.isArray(value.analysts)
    ? value.analysts.filter(
        (item): item is AnalystKind =>
          item === "market" ||
          item === "social" ||
          item === "news" ||
          item === "fundamentals"
      )
    : []
  return {
    ...DEFAULT_ANALYZE_SETTINGS,
    ...value,
    analysts: analysts.length > 0 ? analysts : DEFAULT_ANALYZE_SETTINGS.analysts,
    temperature:
      typeof value.temperature === "number" && Number.isFinite(value.temperature)
        ? value.temperature
        : value.temperature === null
          ? null
          : DEFAULT_ANALYZE_SETTINGS.temperature,
  }
}

function normalizeSettings(raw: unknown): Settings {
  const value = (raw ?? {}) as Settings
  return {
    ...value,
    analyze: normalizeAnalyzeSettings(value.analyze),
    paths: {
      data: value.paths?.data ?? "",
      db: value.paths?.db ?? "",
      qlib: value.paths?.qlib ?? "",
      config: value.paths?.config ?? value.paths?.system ?? "",
      analyze: value.paths?.analyze ?? "",
      system: value.paths?.system ?? value.paths?.config ?? "",
    },
  }
}

export async function querySettings(): Promise<Settings> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "settings.get" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return normalizeSettings(await response.json())
}

export async function updateSettings(patch: SettingsPatch): Promise<Settings> {
  const response = await fetch(apiUrl("/api/commands"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "settings.update", settings: patch }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const job = (await response.json()) as Job
  if (job.status === "succeeded" && job.result) {
    return normalizeSettings(job.result)
  }
  if (job.status === "failed") {
    throw new Error(job.error || "保存失败")
  }
  throw new Error("设置已提交，但还没有写完")
}

export type JsonSchemaOption = {
  value: string
  label: string
  description?: string
}

export type JsonSchema = {
  type?: string | string[]
  title?: string
  description?: string
  properties?: Record<string, JsonSchema>
  required?: string[]
  enum?: unknown[]
  minimum?: number
  maximum?: number
  minLength?: number
  readOnly?: boolean
  items?: JsonSchema
  "x-secret"?: boolean
  "x-widget"?: string
  "x-emptyToken"?: string
  "x-options"?: JsonSchemaOption[]
  "x-visibleWhen"?: Record<string, string[]>
}

export type SettingsSection = {
  id: string
  title: string
  description: string
  schema: JsonSchema
  schema_version: number
  read_only: boolean
  updated_at: string
  values: Record<string, unknown>
}

export type SettingsModule = {
  id: string
  title: string
  description: string
  sort_order: number
  sections: SettingsSection[]
}

export type SettingsCatalog = {
  modules: SettingsModule[]
  paths: Settings["paths"]
}

export type SettingsSectionView = SettingsSection & {
  module: string
  module_title: string
}

export async function querySettingsCatalog(): Promise<SettingsCatalog> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "settings.catalog" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as SettingsCatalog
}

export async function updateSettingsSection(
  module: string,
  section: string,
  values: Record<string, unknown>
): Promise<SettingsSectionView> {
  const response = await fetch(apiUrl("/api/commands"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "settings.update",
      module,
      section,
      values,
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const job = (await response.json()) as Job
  if (job.status === "succeeded" && job.result) {
    return job.result as SettingsSectionView
  }
  if (job.status === "failed") {
    throw new Error(job.error || "保存失败")
  }
  throw new Error("设置已提交，但还没有写完")
}

export async function submitQuotesSync(pool = "default"): Promise<Job> {
  return waitForJob(await postCommand({ type: "quotes.sync", pool }))
}

async function postCommand(payload: Record<string, unknown>): Promise<Job> {
  const response = await fetch(apiUrl("/api/commands"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as Job
}

export async function waitForJob(job: Job): Promise<Job> {
  if (job.status === "succeeded") {
    return job
  }
  if (job.status === "failed") {
    throw new Error(job.error || "任务失败")
  }
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

export async function createPool(id: string, name: string): Promise<Job> {
  return waitForJob(await postCommand({ type: "pool.create", pool: id, name }))
}

export async function deletePool(id: string): Promise<Job> {
  return waitForJob(await postCommand({ type: "pool.delete", pool: id }))
}

export async function addPoolCodes(pool: string, codes: string): Promise<Job> {
  return waitForJob(await postCommand({ type: "pool.add", pool, codes }))
}

export async function addPoolIndex(
  pool: string,
  index: string,
  replace = false
): Promise<Job> {
  return waitForJob(
    await postCommand({
      type: replace ? "pool.set" : "pool.add",
      pool,
      index,
    })
  )
}

export async function removePoolCodes(pool: string, codes: string[]): Promise<Job> {
  return waitForJob(await postCommand({ type: "pool.remove", pool, codes }))
}

export async function addStockCodes(codes: string): Promise<Job> {
  return waitForJob(await postCommand({ type: "stock.add", codes }))
}

export async function addStockIndex(index: string): Promise<Job> {
  return waitForJob(await postCommand({ type: "stock.add", index }))
}

export async function removeStockCodes(codes: string[]): Promise<Job> {
  return waitForJob(await postCommand({ type: "stock.remove", codes }))
}

export async function submitAnalyzeRun(input: {
  pool: string
  code: string
  date: string
  analysts: AnalystKind[]
}): Promise<Job> {
  return postCommand({
    type: "analyze.run",
    pool: input.pool,
    code: input.code,
    date: input.date,
    analysts: input.analysts,
  })
}

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

export type AnalyzeReportList = {
  count: number
  reports: AnalyzeReportSummary[]
}

export type AnalyzeReportDetail = AnalyzeReportSummary & {
  meta?: AnalyzeReportSummary
  complete_report?: string | null
  sections?: Record<string, string | null | undefined>
}

export async function listAnalyzeReports(input?: {
  pool?: string
  code?: string
}): Promise<AnalyzeReportList> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "analyze.list",
      ...(input?.pool ? { pool: input.pool } : {}),
      ...(input?.code ? { code: input.code } : {}),
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const body = (await response.json()) as Partial<AnalyzeReportList>
  const reports = Array.isArray(body.reports) ? body.reports : []
  return { count: body.count ?? reports.length, reports }
}

export async function getAnalyzeReport(input: {
  code: string
  date: string
  run_id?: string
}): Promise<AnalyzeReportDetail> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "analyze.get",
      code: input.code,
      date: input.date,
      ...(input.run_id ? { run_id: input.run_id } : {}),
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const raw = (await response.json()) as AnalyzeReportDetail
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

export async function listJobs(): Promise<Job[]> {
  const response = await fetch(apiUrl("/api/jobs"))
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const body = (await response.json()) as { jobs?: Job[] }
  return Array.isArray(body.jobs) ? body.jobs : []
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}`))
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as Job
}

export function watchJob(
  jobId: string,
  onLog: (line: string) => void,
  onDone: (job: Job) => void,
  onError: (message: string) => void
): () => void {
  const source = new EventSource(apiUrl(`/api/jobs/${jobId}/events`))
  let settled = false
  source.onmessage = (event) => {
    const payload: unknown = JSON.parse(event.data)
    if (typeof payload !== "object" || payload === null || !("stream" in payload)) {
      return
    }
    const stream = (payload as { stream: unknown }).stream
    if (stream === "log" && "message" in payload && typeof payload.message === "string") {
      onLog(payload.message)
      return
    }
    if (stream === "status") {
      settled = true
      source.close()
      const data = "data" in payload ? payload.data : undefined
      if (typeof data === "object" && data !== null) {
        onDone(data as Job)
        return
      }
      onError("任务结束，但没有返回结果")
    }
  }
  source.onerror = () => {
    if (settled) {
      return
    }
    settled = true
    source.close()
    onError("与 core 的任务流断开")
  }
  return () => {
    settled = true
    source.close()
  }
}
