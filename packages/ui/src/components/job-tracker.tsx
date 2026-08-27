import { Link } from "react-router"
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  ListTodoIcon,
  XIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { Job } from "@/lib/api"
import {
  isOpenJob,
  jobDisplayName,
  jobStatusLabel,
  jobStatusVariant,
  trackerJobDetail,
} from "@/lib/jobs"

export function JobTracker({
  jobs,
  allJobs,
  overflow,
  onOpen,
  onDismiss,
  onCancel,
}: {
  jobs: Job[]
  allJobs: Job[]
  overflow: number
  onOpen: (jobId: string) => void
  onDismiss: (jobId: string) => void
  onCancel: (jobId: string) => void
}) {
  if (jobs.length === 0) return null

  return (
    <div className="fixed right-4 bottom-4 z-40 w-[min(22rem,calc(100vw-2rem))]">
      <Card className="gap-0 overflow-hidden py-0 shadow-lg">
        <CardHeader className="border-b py-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <ListTodoIcon className="size-4" />
            后台任务
          </CardTitle>
        </CardHeader>
        <CardContent className="divide-y p-0">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center focus-within:bg-muted/50 hover:bg-muted/50"
            >
              <button
                type="button"
                className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 px-4 py-3 text-left outline-none"
                onClick={() => onOpen(job.id)}
              >
                {job.status === "running" ? (
                  <Spinner className="size-4 shrink-0" />
                ) : job.status === "succeeded" ? (
                  <CheckCircle2Icon className="size-4 shrink-0" />
                ) : job.status === "failed" ? (
                  <CircleAlertIcon className="size-4 shrink-0 text-destructive" />
                ) : (
                  <span className="size-4 shrink-0 rounded-full border" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {jobDisplayName(job)}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {trackerJobDetail(allJobs, job)}
                  </span>
                </span>
                <Badge variant={jobStatusVariant(job.status)}>
                  {jobStatusLabel(job.status)}
                </Badge>
              </button>
              {isOpenJob(job.status) ? (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="mr-2"
                  aria-label={`取消任务 ${job.id}`}
                  onClick={() => onCancel(job.id)}
                >
                  <XIcon />
                </Button>
              ) : job.status === "failed" ? (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="mr-2"
                  aria-label={`关闭任务 ${job.id}`}
                  onClick={() => onDismiss(job.id)}
                >
                  <XIcon />
                </Button>
              ) : null}
            </div>
          ))}
          {overflow > 0 ? (
            <Button
              variant="ghost"
              className="w-full rounded-none"
              render={<Link to="/jobs" />}
              nativeButton={false}
            >
              还有 {overflow} 个任务
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
