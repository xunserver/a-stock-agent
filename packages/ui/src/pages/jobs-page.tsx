import { useEffect, useRef, useState } from "react"
import { Link } from "react-router"
import { CircleAlertIcon, ListTodoIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  getJob,
  listJobs,
  watchJob,
  type Job,
  type JobStatus,
} from "@/lib/api"

function isOpenStatus(status: JobStatus) {
  return status === "queued" || status === "running"
}

function statusLabel(status: JobStatus) {
  if (status === "queued") return "排队"
  if (status === "running") return "运行中"
  if (status === "succeeded") return "成功"
  return "失败"
}

function statusVariant(status: JobStatus): "outline" | "secondary" | "default" | "destructive" {
  if (status === "queued") return "outline"
  if (status === "running") return "secondary"
  if (status === "succeeded") return "default"
  return "destructive"
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function readString(source: Record<string, unknown>, key: string): string | null {
  const value = source[key]
  return typeof value === "string" && value.trim() ? value : null
}

function pickJobString(job: Job, key: string): string | null {
  return readString(asRecord(job.result), key) ?? readString(job.command, key)
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

function summarizeError(error: string | null) {
  if (!error) return "—"
  const text = error.replace(/\s+/g, " ").trim()
  if (text.length <= 48) return text
  return `${text.slice(0, 48)}…`
}

function analyzeHref(job: Job): string | null {
  if (job.type !== "analyze.run" || job.status !== "succeeded") {
    return null
  }
  const code = pickJobString(job, "code")
  const date = pickJobString(job, "date")
  const run = pickJobString(job, "run_id")
  if (!code || !date) {
    return null
  }
  const params = new URLSearchParams({ code, date })
  if (run) {
    params.set("run", run)
  }
  return `/analyze?${params.toString()}`
}

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState<string | null>(null)
  const [detail, setDetail] = useState<Job | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const unwatchRef = useRef<(() => void) | null>(null)
  const skipLogsRef = useRef(0)
  const logEndRef = useRef<HTMLDivElement>(null)

  function stopWatch() {
    unwatchRef.current?.()
    unwatchRef.current = null
  }

  async function refresh() {
    const next = await listJobs()
    setJobs(next)
    setError(null)
    return next
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await refresh()
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    const timer = window.setInterval(() => {
      void refresh().catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "加载失败")
      })
    }, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      stopWatch()
    }
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" })
  }, [logs])

  useEffect(() => {
    if (!openId) {
      return
    }
    let cancelled = false
    stopWatch()
    void (async () => {
      try {
        const job = await getJob(openId)
        if (cancelled) {
          return
        }
        setDetail(job)
        setLogs(job.log ?? [])
        if (isOpenStatus(job.status)) {
          skipLogsRef.current = job.log?.length ?? 0
          unwatchRef.current = watchJob(
            job.id,
            (line) => {
              if (skipLogsRef.current > 0) {
                skipLogsRef.current -= 1
                return
              }
              setLogs((prev) => [...prev, line])
            },
            (done) => {
              setDetail(done)
              if (done.log?.length) {
                setLogs(done.log)
              }
            },
            (message) => {
              setError(message)
            }
          )
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "读取任务失败")
        }
      }
    })()
    return () => {
      cancelled = true
      stopWatch()
    }
  }, [openId])

  const href = detail ? analyzeHref(detail) : null

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>无法读取任务</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>任务</CardTitle>
          <CardDescription>
            列表只活在 core 内存里，大约每 2 秒刷新。点一行查看日志。
          </CardDescription>
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
                  <TableHead>id</TableHead>
                  <TableHead>type</TableHead>
                  <TableHead>status</TableHead>
                  <TableHead>创建</TableHead>
                  <TableHead>结束</TableHead>
                  <TableHead>error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className="cursor-pointer"
                    onClick={() => {
                      setDetail(null)
                      setLogs([])
                      setOpenId(job.id)
                    }}
                  >
                    <TableCell className="font-mono">{job.id}</TableCell>
                    <TableCell className="font-mono">{job.type}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(job.status)}>
                        {statusLabel(job.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(job.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(job.finished_at)}
                    </TableCell>
                    <TableCell className="max-w-56 truncate text-muted-foreground">
                      {summarizeError(job.error)}
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
                  任务只活在 core 内存里，重启 core 后列表会空。分析报告仍在分析页。
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button size="sm" render={<Link to="/analyze" />} nativeButton={false}>
                  去分析页
                </Button>
              </EmptyContent>
            </Empty>
          )}
        </CardContent>
      </Card>

      <Sheet
        open={openId !== null}
        onOpenChange={(open) => {
          if (!open) {
            stopWatch()
            setOpenId(null)
            setDetail(null)
            setLogs([])
          }
        }}
      >
        <SheetContent className="sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{detail ? `${detail.type} · ${detail.id}` : "任务详情"}</SheetTitle>
            <SheetDescription>
              {detail ? `创建于 ${formatDateTime(detail.created_at)}` : "正在读取日志。"}
            </SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-4">
            {detail ? (
              <Badge variant={statusVariant(detail.status)} className="w-fit">
                {statusLabel(detail.status)}
              </Badge>
            ) : (
              <Skeleton className="h-5 w-20" />
            )}
            {detail?.error ? (
              <Alert variant="destructive">
                <CircleAlertIcon />
                <AlertTitle>失败原因</AlertTitle>
                <AlertDescription>{detail.error}</AlertDescription>
              </Alert>
            ) : null}
            <ScrollArea className="h-[min(24rem,60vh)] rounded-lg border">
              <pre className="whitespace-pre-wrap p-3 font-mono text-sm">
                {logs.length > 0 ? logs.join("\n") : "还没有日志。"}
              </pre>
              <div ref={logEndRef} />
            </ScrollArea>
          </div>
          {href ? (
            <SheetFooter>
              <Button render={<Link to={href} />} nativeButton={false}>
                打开分析报告
              </Button>
            </SheetFooter>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  )
}
