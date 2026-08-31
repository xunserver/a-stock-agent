import { apiUrl, isJsonObject, requestJson } from "./http"
import { submitCommand, type Job } from "./jobs"

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
> & { api_key?: string }
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

function normalizeAnalyzeSettings(raw: unknown): AnalyzeSettings {
  const value = isJsonObject(raw) ? raw : {}
  const analysts = Array.isArray(value.analysts)
    ? value.analysts.filter(isAnalystKind)
    : []
  return {
    llm_provider: isLlmProvider(value.llm_provider)
      ? value.llm_provider
      : DEFAULT_ANALYZE_SETTINGS.llm_provider,
    deep_think_llm: readString(value.deep_think_llm),
    quick_think_llm: readString(value.quick_think_llm),
    backend_url: readString(value.backend_url),
    api_key_set: readBoolean(value.api_key_set),
    api_key_hint: readString(value.api_key_hint),
    output_language:
      value.output_language === "English" ? "English" : "Chinese",
    analysts:
      analysts.length > 0 ? analysts : DEFAULT_ANALYZE_SETTINGS.analysts,
    max_debate_rounds: readNumber(
      value.max_debate_rounds,
      DEFAULT_ANALYZE_SETTINGS.max_debate_rounds
    ),
    max_risk_discuss_rounds: readNumber(
      value.max_risk_discuss_rounds,
      DEFAULT_ANALYZE_SETTINGS.max_risk_discuss_rounds
    ),
    temperature:
      value.temperature === null
        ? null
        : typeof value.temperature === "number" &&
            Number.isFinite(value.temperature)
          ? value.temperature
          : DEFAULT_ANALYZE_SETTINGS.temperature,
    checkpoint_enabled: readBoolean(value.checkpoint_enabled),
  }
}
function normalizeSettings(raw: unknown): Settings {
  const value = isJsonObject(raw) ? raw : {}
  const quotes = isJsonObject(value.quotes) ? value.quotes : {}
  const paths = isJsonObject(value.paths) ? value.paths : {}
  const config = readString(paths.config) || readString(paths.system)
  const system = readString(paths.system) || config
  return {
    pool: readString(value.pool),
    adjust:
      value.adjust === "qfq" || value.adjust === "hfq" ? value.adjust : "",
    quotes: {
      sync_enabled: readBoolean(quotes.sync_enabled),
      sync_time: readString(quotes.sync_time),
      timezone: readString(quotes.timezone),
      sleep: readNumber(quotes.sleep, 0),
    },
    analyze: normalizeAnalyzeSettings(value.analyze),
    paths: {
      data: readString(paths.data),
      db: readString(paths.db),
      qlib: readString(paths.qlib),
      config,
      analyze: readString(paths.analyze),
      system,
    },
  }
}
export async function querySettings(): Promise<Settings> {
  return normalizeSettings(await requestJson<unknown>(apiUrl("/api/settings")))
}
export async function updateSettings(patch: SettingsPatch): Promise<Settings> {
  const job = await submitCommand({ type: "settings.update", settings: patch })
  if (job.status === "succeeded" && job.result)
    return normalizeSettings(job.result)
  if (job.status === "failed") throw new Error(job.error || "保存失败")
  throw new Error("设置已提交，但还没有写完")
}
export function querySettingsCatalog(): Promise<SettingsCatalog> {
  return requestJson<SettingsCatalog>(apiUrl("/api/settings/catalog"))
}
export async function updateSettingsSection(
  module: string,
  section: string,
  values: Record<string, unknown>
): Promise<SettingsSectionView> {
  const job: Job = await submitCommand({
    type: "settings.update",
    module,
    section,
    values,
  })
  if (job.status === "succeeded" && job.result)
    return parseSettingsSectionView(job.result)
  if (job.status === "failed") throw new Error(job.error || "保存失败")
  throw new Error("设置已提交，但还没有写完")
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function readBoolean(value: unknown): boolean {
  return value === true
}

function readNumber(value: unknown, fallback: number): number
function readNumber(value: unknown, fallback: null): number | null
function readNumber(value: unknown, fallback: number | null): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback
}

function isAnalystKind(value: unknown): value is AnalystKind {
  return (
    value === "market" ||
    value === "social" ||
    value === "news" ||
    value === "fundamentals"
  )
}

function isLlmProvider(value: unknown): value is LlmProvider {
  return (
    value === "openai_compatible" ||
    value === "qwen-cn" ||
    value === "deepseek" ||
    value === "glm-cn" ||
    value === "ollama" ||
    value === "openai"
  )
}

function isJsonSchema(value: unknown): value is JsonSchema {
  return isJsonObject(value)
}

function parseSettingsSectionView(value: unknown): SettingsSectionView {
  if (
    !isJsonObject(value) ||
    typeof value.id !== "string" ||
    typeof value.title !== "string" ||
    typeof value.module !== "string" ||
    typeof value.module_title !== "string" ||
    !isJsonSchema(value.schema) ||
    !isJsonObject(value.values)
  ) {
    throw new Error("core 返回了无效的设置数据")
  }
  return {
    id: value.id,
    title: value.title,
    description: readString(value.description),
    module: value.module,
    module_title: value.module_title,
    schema: value.schema,
    schema_version: readNumber(value.schema_version, 1) ?? 1,
    read_only: readBoolean(value.read_only),
    updated_at: readString(value.updated_at),
    values: value.values,
  }
}
