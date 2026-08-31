import { Link } from "react-router"
import { CalendarClockIcon, PencilIcon, PlayIcon, PlusIcon } from "lucide-react"

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
import type { Automation } from "@/lib/api"
import { formatJobDateTime, jobStatusLabel, jobStatusVariant } from "@/lib/jobs"

import { scheduleLabel } from "./helpers"

type Props = {
  items: Automation[]
  loading: boolean
  onEdit: (item: Automation | "new") => void
  onRun: (item: Automation) => void
  onToggle: (item: Automation) => void
}

export function AutomationListCard({
  items,
  loading,
  onEdit,
  onRun,
  onToggle,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>自动任务</CardTitle>
        <CardDescription>
          按每日、每周或 A 股交易日规则自动提交任务，执行历史永久保留。
        </CardDescription>
        <CardAction>
          <Button size="sm" onClick={() => onEdit("new")}>
            <PlusIcon data-icon="inline-start" />
            新建自动任务
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {loading ? (
          <AutomationListSkeleton />
        ) : items.length ? (
          <AutomationTable
            items={items}
            onEdit={onEdit}
            onRun={onRun}
            onToggle={onToggle}
          />
        ) : (
          <AutomationListEmpty />
        )}
      </CardContent>
    </Card>
  )
}

function AutomationListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  )
}

function AutomationListEmpty() {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <CalendarClockIcon className="size-8 text-muted-foreground" />
      <div>
        <div className="font-medium">还没有自动任务</div>
        <div className="text-sm text-muted-foreground">
          新建任务后，core 会按规则自动提交执行。
        </div>
      </div>
    </div>
  )
}

function AutomationTable({
  items,
  onEdit,
  onRun,
  onToggle,
}: Omit<Props, "loading">) {
  return (
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
                  onCheckedChange={() => onToggle(item)}
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
              {item.enabled ? formatJobDateTime(item.next_run_at) : "已停用"}
            </TableCell>
            <TableCell>
              <div className="flex justify-end gap-1">
                <Button
                  size="icon-sm"
                  variant="ghost"
                  title="立即运行"
                  onClick={() => onRun(item)}
                >
                  <PlayIcon />
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  title="编辑"
                  onClick={() => onEdit(item)}
                >
                  <PencilIcon />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
