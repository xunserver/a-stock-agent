import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Job } from "@/lib/api"
import {
  formatJobDateTime,
  jobStatusLabel,
  jobStatusVariant,
  summarizeJobError,
} from "@/lib/jobs"

type Props = {
  count: number
  date: string
  runs: Job[]
  onDateChange: (date: string) => void
  onOpen: (id: string) => void
}

export function AutomationRunHistory({
  count,
  date,
  runs,
  onDateChange,
  onOpen,
}: Props) {
  return (
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
              onChange={(event) => onDateChange(event.target.value)}
            />
          </div>
          {date ? (
            <Button variant="outline" onClick={() => onDateChange("")}>
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
                  onClick={() => onOpen(job.id)}
                >
                  <TableCell>
                    <Badge variant={jobStatusVariant(job.status)}>
                      {jobStatusLabel(job.status)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {job.trigger === "scheduled" ? "定时触发" : "立即运行"}
                  </TableCell>
                  <TableCell>{formatJobDateTime(job.scheduled_for)}</TableCell>
                  <TableCell>{formatJobDateTime(job.started_at)}</TableCell>
                  <TableCell>{formatJobDateTime(job.finished_at)}</TableCell>
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
  )
}
