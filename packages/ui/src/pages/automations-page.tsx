import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link, useNavigate, useParams } from "react-router"
import {
  ArchiveIcon,
  CalendarClockIcon,
  CircleAlertIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
} from "lucide-react"

import { useJobs } from "@/components/job-provider"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  archiveAutomation,
  createAutomation,
  getAutomation,
  getAutomationCatalog,
  listAutomationRuns,
  listAutomations,
  runAutomation,
  updateAutomation,
  type Automation,
  type AutomationCommandDefinition,
  type AutomationInput,
  type Job,
  type ScheduleKind,
} from "@/lib/api"
import {
  formatJobDateTime,
  jobStatusLabel,
  jobStatusVariant,
  summarizeJobError,
} from "@/lib/jobs"

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

function scheduleLabel(item: Automation): string {
  if (item.schedule_kind === "trading_day")
    return `A 股交易日 ${item.local_time}`
  if (item.schedule_kind === "daily") return `每天 ${item.local_time}`
  return `${item.weekdays.map((day) => WEEKDAYS[day]).join("、")} ${item.local_time}`
}

export function AutomationsPage() {
  const [items, setItems] = useState<Automation[]>([])
  const [catalog, setCatalog] = useState<AutomationCommandDefinition[]>([])
  const [editing, setEditing] = useState<Automation | "new" | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { trackJob } = useJobs()

  async function refresh() {
    const next = await listAutomations()
    setItems(next)
    setError(null)
  }

  useEffect(() => {
    let cancelled = false
    void Promise.all([listAutomations(), getAutomationCatalog()])
      .then(([next, definitions]) => {
        if (cancelled) return
        setItems(next)
        setCatalog(definitions)
      })
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(
            reason instanceof Error ? reason.message : "加载自动任务失败"
          )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function onToggle(item: Automation) {
    try {
      await updateAutomation(item.id, { enabled: !item.enabled })
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "更新失败")
    }
  }

  async function onRun(item: Automation) {
    try {
      const job = await runAutomation(item.id)
      trackJob(job)
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "提交失败")
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>自动任务操作失败</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>自动任务</CardTitle>
          <CardDescription>
            按每日、每周或 A 股交易日规则自动提交任务，执行历史永久保留。
          </CardDescription>
          <CardAction>
            <Button size="sm" onClick={() => setEditing("new")}>
              <PlusIcon data-icon="inline-start" />
              新建自动任务
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : items.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务</TableHead>
                  <TableHead>规则</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>上次执行</TableHead>
                  <TableHead>下次执行</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Link
                        to={`/automations/${item.id}`}
                        className="font-medium hover:underline"
                      >
                        {item.name}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">
                        {String(item.command.type)}
                      </div>
                    </TableCell>
                    <TableCell>{scheduleLabel(item)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={item.enabled}
                          onCheckedChange={() => void onToggle(item)}
                          aria-label={`${item.name}启用状态`}
                        />
                        <span className="text-xs text-muted-foreground">
                          {item.enabled ? "已启用" : "已停用"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {item.last_status ? (
                        <div className="flex flex-col gap-1">
                          <Badge
                            className="w-fit"
                            variant={jobStatusVariant(item.last_status)}
                          >
                            {jobStatusLabel(item.last_status)}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {formatJobDateTime(item.last_finished_at)}
                          </span>
                        </div>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.enabled
                        ? formatJobDateTime(item.next_run_at)
                        : "已停用"}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          title="立即运行"
                          onClick={() => void onRun(item)}
                        >
                          <PlayIcon />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          title="编辑"
                          onClick={() => setEditing(item)}
                        >
                          <PencilIcon />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <CalendarClockIcon className="size-8 text-muted-foreground" />
              <div>
                <div className="font-medium">还没有自动任务</div>
                <div className="text-sm text-muted-foreground">
                  新建任务后，core 会按规则自动提交执行。
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <AutomationFormDialog
        value={editing}
        catalog={catalog}
        onClose={() => setEditing(null)}
        onSaved={async () => {
          setEditing(null)
          await refresh()
        }}
      />
    </div>
  )
}

export function AutomationDetailPage() {
  const { automationId = "" } = useParams()
  const navigate = useNavigate()
  const { openJob, trackJob } = useJobs()
  const [item, setItem] = useState<Automation | null>(null)
  const [runs, setRuns] = useState<Job[]>([])
  const [count, setCount] = useState(0)
  const [date, setDate] = useState("")
  const [editing, setEditing] = useState<Automation | null>(null)
  const [catalog, setCatalog] = useState<AutomationCommandDefinition[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    const [automation, history] = await Promise.all([
      getAutomation(automationId),
      listAutomationRuns(automationId, date || undefined),
    ])
    setItem(automation)
    setRuns(history.jobs)
    setCount(history.count)
    setError(null)
  }

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      getAutomation(automationId),
      listAutomationRuns(automationId, date || undefined),
      getAutomationCatalog(),
    ])
      .then(([automation, history, definitions]) => {
        if (cancelled) return
        setItem(automation)
        setRuns(history.jobs)
        setCount(history.count)
        setCatalog(definitions)
      })
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "加载失败")
      })
    return () => {
      cancelled = true
    }
  }, [automationId, date])

  useEffect(() => {
    if (
      !runs.some((job) => job.status === "queued" || job.status === "running")
    )
      return
    const timer = window.setInterval(
      () => void refresh().catch(() => undefined),
      2000
    )
    return () => window.clearInterval(timer)
  }, [runs, automationId, date])

  if (!item && !error) return <Skeleton className="h-72 w-full" />

  async function onRun() {
    try {
      const job = await runAutomation(automationId)
      trackJob(job)
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "提交失败")
    }
  }

  async function onArchive() {
    if (!window.confirm("归档后任务不会再运行，但历史记录会永久保留。继续吗？"))
      return
    try {
      await archiveAutomation(automationId)
      navigate("/automations")
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "归档失败")
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>无法读取自动任务</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {item ? (
        <>
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>{item.name}</CardTitle>
                <CardDescription>
                  {item.description || "没有说明"} · {scheduleLabel(item)}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(item)}
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button size="sm" onClick={() => void onRun()}>
                  <PlayIcon data-icon="inline-start" />
                  立即运行
                </Button>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Summary
                label="启用状态"
                value={item.enabled ? "已启用" : "已停用"}
              />
              <Summary
                label="命令"
                value={String(item.command.type || "—")}
                mono
              />
              <Summary
                label="上次计划"
                value={formatJobDateTime(item.last_run_at)}
              />
              <Summary
                label="下次计划"
                value={formatJobDateTime(item.next_run_at)}
              />
              {item.calendar_status && item.calendar_status !== "ok" ? (
                <div className="sm:col-span-2 lg:col-span-4">
                  <Alert variant="destructive">
                    <CircleAlertIcon />
                    <AlertTitle>调度暂不可用</AlertTitle>
                    <AlertDescription>{item.calendar_status}</AlertDescription>
                  </Alert>
                </div>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row items-end justify-between gap-4">
              <div>
                <CardTitle>执行历史</CardTitle>
                <CardDescription>
                  共 {count} 次执行。可按创建日期筛选，点击一行查看完整日志。
                </CardDescription>
              </div>
              <div className="flex items-end gap-2">
                <div className="grid gap-1">
                  <Label htmlFor="run-date">日期</Label>
                  <Input
                    id="run-date"
                    type="date"
                    value={date}
                    onChange={(event) => setDate(event.target.value)}
                  />
                </div>
                {date ? (
                  <Button variant="outline" onClick={() => setDate("")}>
                    清除
                  </Button>
                ) : null}
              </div>
            </CardHeader>
            <CardContent>
              {runs.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>状态</TableHead>
                      <TableHead>来源</TableHead>
                      <TableHead>计划时刻</TableHead>
                      <TableHead>开始</TableHead>
                      <TableHead>结束</TableHead>
                      <TableHead>错误</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((job) => (
                      <TableRow
                        key={job.id}
                        className="cursor-pointer"
                        onClick={() => openJob(job.id)}
                      >
                        <TableCell>
                          <Badge variant={jobStatusVariant(job.status)}>
                            {jobStatusLabel(job.status)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {job.trigger === "scheduled"
                            ? "定时触发"
                            : "立即运行"}
                        </TableCell>
                        <TableCell>
                          {formatJobDateTime(job.scheduled_for)}
                        </TableCell>
                        <TableCell>
                          {formatJobDateTime(job.started_at)}
                        </TableCell>
                        <TableCell>
                          {formatJobDateTime(job.finished_at)}
                        </TableCell>
                        <TableCell className="max-w-64 truncate">
                          {summarizeJobError(job.error)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  这个日期没有执行记录。
                </div>
              )}
            </CardContent>
          </Card>
          <div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void onArchive()}
            >
              <ArchiveIcon data-icon="inline-start" />
              归档自动任务
            </Button>
          </div>
          <AutomationFormDialog
            value={editing}
            catalog={catalog}
            onClose={() => setEditing(null)}
            onSaved={async () => {
              setEditing(null)
              await refresh()
            }}
          />
        </>
      ) : null}
    </div>
  )
}

function Summary({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={mono ? "mt-1 font-mono text-sm" : "mt-1 text-sm font-medium"}
      >
        {value}
      </div>
    </div>
  )
}

type Draft = AutomationInput & { command: Record<string, string> }

function blankDraft(catalog: AutomationCommandDefinition[]): Draft {
  const definition = catalog[0]
  return {
    name: "",
    description: "",
    command: commandDefaults(definition),
    schedule_kind: "trading_day",
    local_time: "16:10",
    timezone: "Asia/Shanghai",
    weekdays: [0, 1, 2, 3, 4],
    enabled: true,
    misfire_policy: "run_once",
  }
}

function commandDefaults(
  definition: AutomationCommandDefinition | undefined
): Record<string, string> {
  if (!definition) return { type: "quotes.sync", pool: "default" }
  return Object.fromEntries([
    ["type", definition.type],
    ...definition.fields.map((field) => [field.name, field.default ?? ""]),
  ])
}

function AutomationFormDialog({
  value,
  catalog,
  onClose,
  onSaved,
}: {
  value: Automation | "new" | null
  catalog: AutomationCommandDefinition[]
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [draft, setDraft] = useState<Draft>(() => blankDraft(catalog))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!value) return
    if (value === "new") {
      setDraft(blankDraft(catalog))
    } else {
      setDraft({
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
      })
    }
    setError(null)
  }, [value, catalog])

  const definition = useMemo(
    () => catalog.find((item) => item.type === draft.command.type),
    [catalog, draft.command.type]
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const command = Object.fromEntries(
      Object.entries(draft.command).filter(
        ([key, item]) => key === "type" || item.trim() !== ""
      )
    )
    const payload: AutomationInput = { ...draft, command }
    try {
      if (value === "new") await createAutomation(payload)
      else if (value) await updateAutomation(value.id, payload)
      await onSaved()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={value !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>
              {value === "new" ? "新建自动任务" : "编辑自动任务"}
            </DialogTitle>
            <DialogDescription>
              自动任务到点后会提交普通 Job，每一次执行和日志都会永久保留。
            </DialogDescription>
          </DialogHeader>
          {error ? (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <div className="grid gap-2">
            <Label htmlFor="automation-name">名称</Label>
            <Input
              id="automation-name"
              value={draft.name}
              required
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  name: event.target.value,
                }))
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
              onChange={(event) => {
                const next = catalog.find(
                  (item) => item.type === event.target.value
                )
                setDraft((current) => ({
                  ...current,
                  command: commandDefaults(next),
                }))
              }}
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
                  placeholder={
                    field.name === "codes" ? "例如 600519, 000001" : ""
                  }
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
                  <label
                    key={label}
                    className="flex items-center gap-1.5 text-sm"
                  >
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
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
