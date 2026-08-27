import { Link } from "react-router"
import { CircleAlertIcon, ListTodoIcon } from "lucide-react"

import { useJobs } from "@/components/job-provider"
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
  formatJobDateTime,
  jobDisplayName,
  jobStatusLabel,
  jobStatusVariant,
  summarizeJobError,
} from "@/lib/jobs"

export function JobsPage() {
  const { jobs, error, loading, openJob } = useJobs()

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
                  <TableHead>名称</TableHead>
                  <TableHead>状态</TableHead>
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
                  任务只活在 core 内存里，重启 core
                  后列表会空。分析报告仍在分析页。
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
