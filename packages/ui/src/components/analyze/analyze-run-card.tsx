import type { RefObject } from "react"
import { FileTextIcon } from "lucide-react"

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
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { FieldDescription } from "@/components/ui/field"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Job } from "@/lib/api"
import { jobQueuedHint, jobStatusLabel, jobStatusVariant } from "@/lib/jobs"

export function AnalyzeRunCard({
  job,
  jobs,
  logs,
  decision,
  logEndRef,
  onOpenReport,
}: {
  job: Job | null
  jobs: Job[]
  logs: string[]
  decision: string | null
  logEndRef: RefObject<HTMLDivElement | null>
  onOpenReport: (job: Job) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>本次运行</CardTitle>
        <CardDescription>
          {job
            ? [job.id, jobQueuedHint(jobs, job)].filter(Boolean).join(" · ")
            : "提交后会在这里跟日志。刷新页面会接上还没结束的 analyze.run。"}
        </CardDescription>
        {job ? (
          <CardAction>
            <Badge variant={jobStatusVariant(job.status)}>
              {jobStatusLabel(job.status)}
            </Badge>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        {job ? (
          <div className="flex flex-col gap-3">
            <ScrollArea className="h-72 rounded-lg border">
              <pre className="p-3 font-mono text-sm whitespace-pre-wrap">
                {logs.length > 0 ? logs.join("\n") : "还没有日志。"}
              </pre>
              <div ref={logEndRef} />
            </ScrollArea>
            {job.status === "succeeded" ? (
              <div className="flex flex-col gap-2">
                <CardTitle>{decision || "已完成"}</CardTitle>
                <FieldDescription>
                  决策来自这次运行。完整分段在下面的历史报告里。
                </FieldDescription>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-fit"
                  onClick={() => onOpenReport(job)}
                >
                  查看报告
                </Button>
              </div>
            ) : null}
          </div>
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FileTextIcon />
              </EmptyMedia>
              <EmptyTitle>还没有正在看的任务</EmptyTitle>
              <EmptyDescription>
                点「开始分析」之后，日志会出现在这里。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>
    </Card>
  )
}
