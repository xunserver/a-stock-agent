import { useEffect, useRef, useState } from "react"
import { Link } from "react-router"
import { ListTodoIcon } from "lucide-react"

import { useJobs } from "@/components/job-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  formatJobDateTime,
  jobDisplayName,
  jobStatusLabel,
  jobStatusVariant,
  summarizeJobError,
} from "@/lib/jobs"
import { listJobs, type Job } from "@/lib/api"
import { notify } from "@/lib/notify"

export function JobsPage() {
  const { openJob } = useJobs()
  const [jobs, setJobs] = useState<Job[]>([])
  const [date, setDate] = useState("")
  const [trigger, setTrigger] = useState("")
  const [loading, setLoading] = useState(true)
  const lastErrorRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function refresh() {
      try {
        const next = await listJobs({
          date: date || undefined,
          trigger: trigger || undefined,
        })
        if (!cancelled) {
          setJobs(next)
          lastErrorRef.current = null
        }
      } catch (reason: unknown) {
        if (!cancelled) {
          const message =
            reason instanceof Error ? reason.message : "加载任务失败"
          if (lastErrorRef.current !== message) {
            lastErrorRef.current = message
            notify.error("无法读取任务", { description: message })
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [date, trigger])

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex-row items-end justify-between gap-4">
          <div>
            <CardTitle>任务</CardTitle>
            <CardDescription>
              手动与自动执行记录永久保留，大约每 2 秒刷新。点一行查看日志。
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Input
              type="date"
              value={date}
              aria-label="按日期筛选"
              onChange={(event) => setDate(event.target.value)}
            />
            <select
              className="h-8 rounded-lg border border-input bg-background px-2.5 text-sm"
              value={trigger}
              aria-label="按来源筛选"
              onChange={(event) => setTrigger(event.target.value)}
            >
              <option value="">全部来源</option>
              <option value="manual">手动任务</option>
              <option value="scheduled">定时触发</option>
              <option value="automation_manual">自动任务立即运行</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {loading && jobs.length === 0 ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : jobs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead>创建</TableHead>
                  <TableHead>结束</TableHead>
                  <TableHead>错误</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className="cursor-pointer"
                    onClick={() => openJob(job.id)}
                  >
                    <TableCell>
                      <div className="font-medium">{jobDisplayName(job)}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {job.id} · {job.type}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={jobStatusVariant(job.status)}>
                        {jobStatusLabel(job.status)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {job.automation_id ? (
                        <Link
                          to={`/automations/${job.automation_id}`}
                          className="hover:underline"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {job.trigger === "scheduled"
                            ? "定时触发"
                            : "立即运行"}
                        </Link>
                      ) : (
                        "手动"
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatJobDateTime(job.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatJobDateTime(job.finished_at)}
                    </TableCell>
                    <TableCell className="max-w-56 truncate text-muted-foreground">
                      {job.status === "cancelled"
                        ? "—"
                        : summarizeJobError(job.error)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <ListTodoIcon />
                </EmptyMedia>
                <EmptyTitle>还没有任务</EmptyTitle>
                <EmptyDescription>
                  当前筛选条件下还没有任务记录。
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button
                  size="sm"
                  render={<Link to="/analyze" />}
                  nativeButton={false}
                >
                  去分析页
                </Button>
              </EmptyContent>
            </Empty>
          )}
        </CardContent>
      </Card>
    </div>
  )
}