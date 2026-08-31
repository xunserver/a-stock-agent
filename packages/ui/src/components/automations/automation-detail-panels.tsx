import { CircleAlertIcon, PencilIcon, PlayIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { Automation } from "@/lib/api"
import { formatJobDateTime } from "@/lib/jobs"

import { scheduleLabel } from "./helpers"

export function AutomationSummary({
  item,
  onEdit,
  onRun,
}: {
  item: Automation
  onEdit: () => void
  onRun: () => void
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>{item.name}</CardTitle>
          <CardDescription>
            {item.description || "没有说明"} · {scheduleLabel(item)}
          </CardDescription>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>
            <PencilIcon data-icon="inline-start" />
            编辑
          </Button>
          <Button size="sm" onClick={onRun}>
            <PlayIcon data-icon="inline-start" />
            立即运行
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Summary label="启用状态" value={item.enabled ? "已启用" : "已停用"} />
        <Summary label="命令" value={String(item.command.type || "—")} mono />
        <Summary label="上次计划" value={formatJobDateTime(item.last_run_at)} />
        <Summary label="下次计划" value={formatJobDateTime(item.next_run_at)} />
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
  )
}

export function Summary({
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
