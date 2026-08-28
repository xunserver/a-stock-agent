import { useState } from "react"
import { Link } from "react-router"
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleAlertIcon,
  ListTodoIcon,
  XIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { Job } from "@/lib/api"
import {
  isOpenJob,
  jobDisplayName,
  jobStatusLabel,
  jobStatusVariant,
  trackerJobDetail,
} from "@/lib/jobs"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

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
  const [collapsed, setCollapsed] = useState(
    () => readUiPrefs().jobTrackerCollapsed
  )

  if (jobs.length === 0) return null

  const running = jobs.some((job) => isOpenJob(job.status))

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current
      patchUiPrefs({ jobTrackerCollapsed: next })
      return next
    })
  }

  return (
    <div className="fixed right-4 bottom-4 z-40 w-[min(22rem,calc(100vw-2rem))]">
      <Card className="gap-0 overflow-hidden py-0 shadow-lg">
        <CardHeader
          className={cn("items-center py-3", !collapsed && "border-b")}
        >
          <CardTitle className="flex items-center gap-2 text-sm">
            {running ? (
              <Spinner className="size-4" />
            ) : (
              <ListTodoIcon className="size-4" />
            )}
            后台任务
            {collapsed ? (
              <Badge variant="secondary">{jobs.length}</Badge>
            ) : null}
          </CardTitle>
          <CardAction>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-expanded={!collapsed}
              aria-label={collapsed ? "展开后台任务" : "缩小后台任务"}
              onClick={toggleCollapsed}
            >
              {collapsed ? <ChevronUpIcon /> : <ChevronDownIcon />}
            </Button>
          </CardAction>
        </CardHeader>
        {collapsed ? null : (
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
        )}
      </Card>
    </div>
  )
}
