import type { Dispatch, SetStateAction } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { AutomationCommandDefinition, ScheduleKind } from "@/lib/api"

import { commandDefaults, type Draft, WEEKDAYS } from "./helpers"

type Props = {
  catalog: AutomationCommandDefinition[]
  definition: AutomationCommandDefinition | undefined
  draft: Draft
  setDraft: Dispatch<SetStateAction<Draft>>
}

export function AutomationFormFields({
  catalog,
  definition,
  draft,
  setDraft,
}: Props) {
  return (
    <>
      <div className="grid gap-2">
        <Label htmlFor="automation-name">名称</Label>
        <Input
          id="automation-name"
          value={draft.name}
          required
          onChange={(event) =>
            setDraft((current) => ({ ...current, name: event.target.value }))
          }
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="automation-description">说明</Label>
        <Input
          id="automation-description"
          value={draft.description}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              description: event.target.value,
            }))
          }
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="automation-command">任务类型</Label>
        <select
          id="automation-command"
          className="h-8 rounded-lg border border-input bg-background px-2.5 text-sm"
          value={draft.command.type}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              command: commandDefaults(
                catalog.find((item) => item.type === event.target.value)
              ),
            }))
          }
        >
          {catalog.map((item) => (
            <option key={item.type} value={item.type}>
              {item.label}
            </option>
          ))}
        </select>
        {definition ? (
          <p className="text-xs text-muted-foreground">
            {definition.description}
          </p>
        ) : null}
      </div>
      {definition?.fields.map((field) => (
        <div className="grid gap-2" key={field.name}>
          <Label htmlFor={`command-${field.name}`}>{field.label}</Label>
          {field.kind === "select" ? (
            <select
              id={`command-${field.name}`}
              className="h-8 rounded-lg border border-input bg-background px-2.5 text-sm"
              value={draft.command[field.name] ?? ""}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  command: {
                    ...current.command,
                    [field.name]: event.target.value,
                  },
                }))
              }
            >
              {field.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <Input
              id={`command-${field.name}`}
              value={draft.command[field.name] ?? ""}
              required={!field.optional}
              placeholder={field.name === "codes" ? "例如 600519, 000001" : ""}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  command: {
                    ...current.command,
                    [field.name]: event.target.value,
                  },
                }))
              }
            />
          )}
        </div>
      ))}
      <AutomationScheduleFields draft={draft} setDraft={setDraft} />
    </>
  )
}

function AutomationScheduleFields({
  draft,
  setDraft,
}: Pick<Props, "draft" | "setDraft">) {
  return (
    <>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="schedule-kind">调度规则</Label>
          <select
            id="schedule-kind"
            className="h-8 rounded-lg border border-input bg-background px-2.5 text-sm"
            value={draft.schedule_kind}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                schedule_kind: event.target.value as ScheduleKind,
              }))
            }
          >
            <option value="daily">每天</option>
            <option value="weekly">每周</option>
            <option value="trading_day">A 股交易日</option>
          </select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="schedule-time">执行时刻</Label>
          <Input
            id="schedule-time"
            type="time"
            value={draft.local_time}
            required
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                local_time: event.target.value,
              }))
            }
          />
        </div>
      </div>
      {draft.schedule_kind === "weekly" ? (
        <div className="grid gap-2">
          <Label>每周执行日</Label>
          <div className="flex flex-wrap gap-2">
            {WEEKDAYS.map((label, day) => (
              <label key={label} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={draft.weekdays?.includes(day)}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      weekdays: event.target.checked
                        ? [...(current.weekdays ?? []), day].sort()
                        : (current.weekdays ?? []).filter(
                            (item) => item !== day
                          ),
                    }))
                  }
                />
                {label}
              </label>
            ))}
          </div>
        </div>
      ) : null}
      <div className="grid gap-2">
        <Label htmlFor="schedule-timezone">时区</Label>
        <Input
          id="schedule-timezone"
          value={draft.timezone}
          required
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              timezone: event.target.value,
            }))
          }
        />
      </div>
      <div className="flex items-center justify-between rounded-lg border p-3">
        <div>
          <div className="text-sm font-medium">启用自动执行</div>
          <div className="text-xs text-muted-foreground">
            停用后保留配置和全部历史。
          </div>
        </div>
        <Switch
          checked={draft.enabled}
          onCheckedChange={(enabled) =>
            setDraft((current) => ({ ...current, enabled }))
          }
        />
      </div>
    </>
  )
}
