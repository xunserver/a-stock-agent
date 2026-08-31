import type {
  Automation,
  AutomationCommandDefinition,
  AutomationInput,
} from "@/lib/api"

export const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

export type Draft = AutomationInput & { command: Record<string, string> }

export function scheduleLabel(item: Automation): string {
  if (item.schedule_kind === "trading_day")
    return `A 股交易日 ${item.local_time}`
  if (item.schedule_kind === "daily") return `每天 ${item.local_time}`
  return `${item.weekdays.map((day) => WEEKDAYS[day]).join("、")} ${item.local_time}`
}

export function blankDraft(catalog: AutomationCommandDefinition[]): Draft {
  return {
    name: "",
    description: "",
    command: commandDefaults(catalog[0]),
    schedule_kind: "trading_day",
    local_time: "16:10",
    timezone: "Asia/Shanghai",
    weekdays: [0, 1, 2, 3, 4],
    enabled: true,
    misfire_policy: "run_once",
  }
}

export function commandDefaults(
  definition: AutomationCommandDefinition | undefined
): Record<string, string> {
  if (!definition) return { type: "quotes.sync", pool: "default" }
  return Object.fromEntries([
    ["type", definition.type],
    ...definition.fields.map((field) => [field.name, field.default ?? ""]),
  ])
}

export function automationDraft(value: Automation): Draft {
  return {
    name: value.name,
    description: value.description,
    command: Object.fromEntries(
      Object.entries(value.command).map(([key, item]) => [
        key,
        Array.isArray(item) ? item.join(",") : String(item ?? ""),
      ])
    ),
    schedule_kind: value.schedule_kind,
    local_time: value.local_time,
    timezone: value.timezone,
    weekdays: value.weekdays,
    enabled: value.enabled,
    misfire_policy: value.misfire_policy,
  }
}
