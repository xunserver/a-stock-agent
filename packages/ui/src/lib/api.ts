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

export async function queryQlibOverview(pool: string): Promise<QlibOverview> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "qlib.overview", pool }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as QlibOverview
}

export async function listQlibRuns(pool: string): Promise<QlibRun[]> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "qlib.runs", pool }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const body = (await response.json()) as { runs: QlibRun[] }
  return body.runs
}

export async function getQlibRun(runId: string): Promise<QlibRun> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "qlib.run.get", run_id: runId }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as QlibRun
}

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

export type CalendarMarket = {
  id: string
  title: string
  status: "active" | "planned" | string
  count: number
  first: string | null
  last: string | null
}

export type CalendarMarkets = {
  count: number
  markets: CalendarMarket[]
}

export type CalendarDay = {
  date: string
  is_trading: boolean
}

export type CalendarMonth = {
  market: string
  title: string
  status: string
  year: number
  month: number
  start: string
  end: string
  trading_days: number
  days: CalendarDay[]
  today: string
  today_is_trading: boolean
  trade_date: string | null
  coverage: {
    count: number
    first: string | null
    last: string | null
  }
}

export async function queryCalendarMarkets(): Promise<CalendarMarkets> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "calendar.markets" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as CalendarMarkets
}

export type CalendarSession = {
  label: string
  start: string
  end: string
}

export type CalendarOverviewMarket = {
  id: string
  title: string
  status: string
  timezone: string
  today: string
  today_is_trading: boolean
  trade_date: string | null
  in_session: boolean
  has_calendar: boolean
  sessions: CalendarSession[]
  sessions_note: string | null
}

export type CalendarOverview = {
  markets: CalendarOverviewMarket[]
}

export async function queryCalendarOverview(): Promise<CalendarOverview> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "calendar.overview" }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as CalendarOverview
}

export async function queryCalendarMonth(options: {
  market: string
  year: number
  month: number
}): Promise<CalendarMonth> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "calendar.get",
      market: options.market,
      year: options.year,
      month: options.month,
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as CalendarMonth
}

export type CalendarGridMarket = {
  id: string
  title: string
  badge: string
  status: string
  timezone: string
  today: string
  in_session: boolean
  has_calendar: boolean
  sessions: CalendarSession[]
  sessions_note: string | null
}

export type CalendarGridDay = {
  date: string
  markets: string[]
}

export type CalendarGrid = {
  year: number
  month: number
  start: string
  end: string
  today: string
  days: CalendarGridDay[]
  markets: CalendarGridMarket[]
}

export async function queryCalendarGrid(options?: {
  year: number
  month: number
}): Promise<CalendarGrid> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "calendar.month",
      ...(options ?? {}),
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as CalendarGrid
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
  ticker?: string
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

export type DailyBar = {
  trade_date: string
  open: number | null
  close: number | null
  high: number | null
  low: number | null
  volume: number | null
  amount: number | null
  pct_chg: number | null
  turnover: number | null
  amplitude: number | null
  change_amount: number | null
}

export type StockProfile = {
  code: string
  name: string | null
  industry: string | null
  region: string | null
  list_date: string | null
  total_shares: number | null
  float_shares: number | null
  total_mv: number | null
  float_mv: number | null
  latest_price: number | null
  pre_close: number | null
  avg_price: number | null
  high_limit: number | null
  low_limit: number | null
  volume_ratio: number | null
  outer_vol: number | null
  inner_vol: number | null
  pe_dyn: number | null
  pe_static: number | null
  pb: number | null
  eps: number | null
  bps: number | null
  roe: number | null
  revenue: number | null
  revenue_yoy: number | null
  net_profit: number | null
  net_profit_yoy: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  is_st: number
  is_suspended: number
  suspend_info: string | null
  updated_at: string | null
}

export type QuotesSummary = {
  adjust: string
  bars: number
  first: string | null
  last: string | null
  calendar_as_of: string | null
  missing_sessions: number
}

export type FinancialReport = {
  report_date: string
  report_type?: string | null
  notice_date?: string | null
  eps?: number | null
  bps?: number | null
  roe?: number | null
  revenue?: number | null
  revenue_yoy?: number | null
  net_profit?: number | null
  net_profit_yoy?: number | null
  gross_margin?: number | null
  net_margin?: number | null
  debt_ratio?: number | null
  updated_at?: string | null
}

export type FinancialSummary = {
  count: number
  latest_report_date: string | null
}

export type FinancialStatementSheet = "balance" | "profit" | "cashflow"

export type FinancialStatementSheetSummary = {
  count: number
  latest_report_date: string | null
}

export type FinancialStatementsSummary = Record<
  FinancialStatementSheet,
  FinancialStatementSheetSummary
>

export type FinancialStatementKeyItem = {
  key: string
  label: string
  value: number | string | null
  kind?: "amount" | "percent" | string
  yoy?: number | null
  qoq?: number | null
}

export type FinancialStatementDetail = {
  code: string
  ticker: string
  sheet: FinancialStatementSheet
  report_date: string
  report_type?: string | null
  notice_date?: string | null
  key_items: FinancialStatementKeyItem[]
  payload: Record<string, number | string>
  updated_at?: string | null
}

export type StockDetail = {
  code: string
  ticker: string
  profile: StockProfile
  pools?: StockPoolRef[]
  quotes_summary: QuotesSummary
  latest_bar: DailyBar | null
  bars: DailyBar[]
  bars_weekly?: DailyBar[]
  bars_yearly?: DailyBar[]
  financial_reports?: FinancialReport[]
  financial_summary?: FinancialSummary
  financial_statements_summary?: FinancialStatementsSummary
}

export async function queryStock(code: string): Promise<StockDetail> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "stock.get", code }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as StockDetail
}

export type StockNewsItem = {
  title: string
  summary?: string
  published_at?: string
  source?: string
  url?: string
}

export type StockNews = {
  code: string
  ticker: string
  count: number
  news: StockNewsItem[]
  error?: string | null
}

export async function queryStockNews(code: string): Promise<StockNews> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "stock.news", code }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as StockNews
}

export type StockEventKind =
  "notices" | "research" | "block_trades" | "holder_changes"

export type StockEventItem = {
  title: string
  summary?: string
  published_at?: string
  source?: string
  url?: string
  extra?: Record<string, unknown>
}

export type StockEvents = {
  code: string
  ticker: string
  kind: StockEventKind
  count: number
  events: StockEventItem[]
  error?: string | null
}

export async function queryStockEvents(
  code: string,
  kind: StockEventKind
): Promise<StockEvents> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "stock.events", code, kind }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as StockEvents
}

export type LlmProvider =
  "openai_compatible" | "qwen-cn" | "deepseek" | "glm-cn" | "ollama" | "openai"

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
    analysts:
      analysts.length > 0 ? analysts : DEFAULT_ANALYZE_SETTINGS.analysts,
    temperature:
      typeof value.temperature === "number" &&
      Number.isFinite(value.temperature)
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

export async function submitQuotesSync(
  pool = "default",
  codes?: string[]
): Promise<Job> {
  return submitCommand({
    type: "quotes.sync",
    pool,
    ...(codes && codes.length > 0 ? { codes } : {}),
  })
}

export async function queryFinancialDetail(
  code: string,
  options: { sheet: FinancialStatementSheet; reportDate: string }
): Promise<FinancialStatementDetail> {
  const response = await fetch(apiUrl("/api/queries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "stock.financials.detail",
      code,
      sheet: options.sheet,
      report_date: options.reportDate,
    }),
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as FinancialStatementDetail
}

export async function submitStockSync(
  codes: string[],
  options?: { withStatements?: boolean }
): Promise<Job> {
  return submitCommand({
    type: "stock.sync",
    codes,
    ...(options?.withStatements ? { with_statements: true } : {}),
  })
}

export async function submitCommand(
  payload: Record<string, unknown>
): Promise<Job> {
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

export async function submitQlibRun(
  pool: string,
  workflow: QlibWorkflow
): Promise<Job> {
  return submitCommand({
    type: "qlib.run",
    pool,
    workflow,
    background: true,
  })
}

export async function submitQlibDump(pool: string): Promise<Job> {
  return submitCommand({
    type: "qlib.dump",
    pool,
    background: true,
  })
}

export async function saveQlibWorkflow(
  pool: string,
  workflow: QlibWorkflow
): Promise<Job> {
  return waitForJob(
    await submitCommand({
      type: "qlib.workflow.update",
      pool,
      workflow,
    })
  )
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
  return waitForJob(
    await submitCommand({ type: "pool.create", pool: id, name })
  )
}

export async function deletePool(id: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.delete", pool: id }))
}

export async function addPoolCodes(pool: string, codes: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.add", pool, codes }))
}

export async function addPoolIndex(
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

export async function removePoolCodes(
  pool: string,
  codes: string[]
): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.remove", pool, codes }))
}

export async function reorderPoolMembers(
  pool: string,
  codes: string[]
): Promise<Job> {
  return waitForJob(await submitCommand({ type: "pool.reorder", pool, codes }))
}

export async function addStockCodes(codes: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "stock.add", codes }))
}

export async function addStockIndex(index: string): Promise<Job> {
  return submitCommand({ type: "stock.add", index, background: true })
}

export async function removeStockCodes(codes: string[]): Promise<Job> {
  return waitForJob(await submitCommand({ type: "stock.remove", codes }))
}

export async function submitAnalyzeRun(input: {
  pool: string
  code: string
  date: string
  analysts: AnalystKind[]
}): Promise<Job> {
  return submitCommand({
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

export async function listJobs(filters?: {
  automation_id?: string
  date?: string
  trigger?: string
  limit?: number
  offset?: number
}): Promise<Job[]> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value !== undefined && value !== "") query.set(key, String(value))
  }
  const response = await fetch(
    apiUrl(`/api/jobs${query.size > 0 ? `?${query}` : ""}`)
  )
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  const body = (await response.json()) as { jobs?: Job[] }
  return Array.isArray(body.jobs) ? body.jobs : []
}

export async function listAutomations(): Promise<Automation[]> {
  const response = await fetch(apiUrl("/api/automations"))
  if (!response.ok) throw new Error(await readError(response))
  const body = (await response.json()) as { automations?: Automation[] }
  return Array.isArray(body.automations) ? body.automations : []
}

export async function getAutomation(id: string): Promise<Automation> {
  const response = await fetch(apiUrl(`/api/automations/${id}`))
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as Automation
}

export async function getAutomationCatalog(): Promise<
  AutomationCommandDefinition[]
> {
  const response = await fetch(apiUrl("/api/automations/catalog"))
  if (!response.ok) throw new Error(await readError(response))
  const body = (await response.json()) as {
    commands?: AutomationCommandDefinition[]
  }
  return Array.isArray(body.commands) ? body.commands : []
}

export async function createAutomation(
  input: AutomationInput
): Promise<Automation> {
  const response = await fetch(apiUrl("/api/automations"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as Automation
}

export async function updateAutomation(
  id: string,
  input: Partial<AutomationInput>
): Promise<Automation> {
  const response = await fetch(apiUrl(`/api/automations/${id}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as Automation
}

export async function archiveAutomation(id: string): Promise<Automation> {
  const response = await fetch(apiUrl(`/api/automations/${id}`), {
    method: "DELETE",
  })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as Automation
}

export async function runAutomation(id: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/automations/${id}/run`), {
    method: "POST",
  })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as Job
}

export async function listAutomationRuns(
  id: string,
  date?: string
): Promise<{ jobs: Job[]; count: number }> {
  const query = new URLSearchParams()
  if (date) query.set("date", date)
  const response = await fetch(
    apiUrl(`/api/automations/${id}/runs${query.size ? `?${query}` : ""}`)
  )
  if (!response.ok) throw new Error(await readError(response))
  const body = (await response.json()) as { jobs?: Job[]; count?: number }
  const jobs = Array.isArray(body.jobs) ? body.jobs : []
  return { jobs, count: body.count ?? jobs.length }
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}`))
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as Job
}

export async function cancelJob(jobId: string): Promise<Job> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}/cancel`), {
    method: "POST",
  })
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
    if (
      typeof payload !== "object" ||
      payload === null ||
      !("stream" in payload)
    ) {
      return
    }
    const stream = (payload as { stream: unknown }).stream
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
