import { useEffect, useRef } from "react"
import { Link } from "react-router"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { TickerLink } from "@/components/ticker-link"
import { useJobWatch } from "@/hooks/use-job-watch"
import { type Job } from "@/lib/api"
import {
  analyzeJobHref,
  describeJobParams,
  formatJobDateTime,
  formatTimeoutSeconds,
  isOpenJob,
  jobDisplayName,
  jobStatusLabel,
  jobStatusVariant,
  pickJobCodes,
} from "@/lib/jobs"
import { notify } from "@/lib/notify"

export function JobDetailSheet({
  jobId,
  onOpenChange,
  onDone,
  onRequestCancel,
}: {
  jobId: string | null
  onOpenChange: (open: boolean) => void
  onDone: (job: Job) => void
  onRequestCancel: (jobId: string) => void
}) {
  const { job, logs, error, loading } = useJobWatch(jobId, onDone)
  const logEndRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" })
  }, [logs])
  const href = job ? analyzeJobHref(job) : null
  const codes = job ? pickJobCodes(job) : []
  const params = job ? describeJobParams(job.command) : []
  const failed = job?.status === "failed" ? job.error : null
  const canCancel = job !== null && isOpenJob(job.status)
  const lastNotifiedRef = useRef<string | null>(null)

  useEffect(() => {
    const message = failed ?? error
    if (!message) {
      return
    }
    const key = `${jobId ?? ""}:${message}`
    if (lastNotifiedRef.current === key) {
      return
    }
    lastNotifiedRef.current = key
    notify.error(failed ? "任务失败" : "无法读取任务", {
      description: message,
      coreHint: false,
    })
  }, [error, failed, jobId])

  return (
    <Sheet open={jobId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="z-[60] sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{job ? jobDisplayName(job) : "任务详情"}</SheetTitle>
          <SheetDescription>
            {job
              ? `${job.id} · ${job.type} · 创建于 ${formatJobDateTime(job.created_at)}`
              : "正在读取日志。"}
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-4">
          {job ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={jobStatusVariant(job.status)}>
                {jobStatusLabel(job.status)}
              </Badge>
              <Badge variant="outline">
                超时上限 {formatTimeoutSeconds(job.timeout_seconds)}
              </Badge>
              <Badge variant="outline">
                {job.trigger === "scheduled"
                  ? "定时触发"
                  : job.trigger === "automation_manual"
                    ? "自动任务立即运行"
                    : "手动触发"}
              </Badge>
              {job.scheduled_for ? (
                <Badge variant="outline">
                  计划 {formatJobDateTime(job.scheduled_for)}
                </Badge>
              ) : null}
              {codes.map((code) => (
                <TickerLink key={code} code={code} />
              ))}
            </div>
          ) : loading ? (
            <Skeleton className="h-5 w-24" />
          ) : null}
          {job && params.length > 0 ? (
            <div className="rounded-lg border">
              <div className="border-b px-3 py-2 text-sm font-medium">
                提交参数
              </div>
              <dl className="divide-y">
                {params.map((row) => (
                  <div
                    key={`${row.label}-${row.value}`}
                    className="grid grid-cols-[7rem_1fr] gap-3 px-3 py-2 text-sm"
                  >
                    <dt className="text-muted-foreground">{row.label}</dt>
                    <dd className="min-w-0 font-mono text-xs break-words">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}
          <ScrollArea className="h-[min(24rem,60vh)] rounded-lg border">
            <pre className="p-3 font-mono text-sm whitespace-pre-wrap">
              {logs.length > 0 ? logs.join("\n") : "还没有日志。"}
            </pre>
            <div ref={logEndRef} />
          </ScrollArea>
        </div>
        {href || canCancel ? (
          <SheetFooter>
            {canCancel ? (
              <Button variant="outline" onClick={() => onRequestCancel(job.id)}>
                取消任务
              </Button>
            ) : null}
            {href ? (
              <Button render={<Link to={href} />} nativeButton={false}>
                打开分析报告
              </Button>
            ) : null}
          </SheetFooter>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
