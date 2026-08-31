import { FileTextIcon } from "lucide-react"

import {
  REPORT_SECTIONS,
  type ReportSectionId,
} from "@/components/analyze/analyze-model"
import { TickerLink } from "@/components/ticker-link"
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
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AnalyzeReportDetail, AnalyzeReportSummary } from "@/lib/api"
import { formatJobDateTime } from "@/lib/jobs"

type AnalyzeReportBrowserProps = {
  reports: AnalyzeReportSummary[]
  reportsLoading: boolean
  filterByCode: boolean
  reportLoading: boolean
  opened: AnalyzeReportDetail | null
  section: ReportSectionId
  openedText: string
  canSubmit: boolean
  onToggleFilter: (checked: boolean) => void
  onOpenReport: (code: string, date: string, runId?: string) => void
  onSectionChange: (section: ReportSectionId) => void
  onSubmit: () => void
}

/** Pure historical-report list and reader; fetching and URL state stay in the page. */
export function AnalyzeReportBrowser({
  reports,
  reportsLoading,
  filterByCode,
  reportLoading,
  opened,
  section,
  openedText,
  canSubmit,
  onToggleFilter,
  onOpenReport,
  onSectionChange,
  onSubmit,
}: AnalyzeReportBrowserProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>历史报告</CardTitle>
        <CardDescription>
          报告写在磁盘上。重启 core 后任务列表会空，这里还在。
        </CardDescription>
        <CardAction>
          <Field orientation="horizontal">
            <FieldLabel htmlFor="filter-code">只看当前股票</FieldLabel>
            <Switch
              id="filter-code"
              checked={filterByCode}
              onCheckedChange={onToggleFilter}
            />
          </Field>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          {reportsLoading && reports.length === 0 ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : reports.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>日期</TableHead>
                  <TableHead>决策</TableHead>
                  <TableHead>时间</TableHead>
                  <TableHead className="w-20">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((item) => (
                  <TableRow key={`${item.code}-${item.date}-${item.run_id}`}>
                    <TableCell className="font-mono">
                      <TickerLink code={item.code} />
                    </TableCell>
                    <TableCell>{item.name || "—"}</TableCell>
                    <TableCell className="font-mono">{item.date}</TableCell>
                    <TableCell>{item.decision || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatJobDateTime(item.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() =>
                          onOpenReport(item.code, item.date, item.run_id)
                        }
                      >
                        打开
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileTextIcon />
                </EmptyMedia>
                <EmptyTitle>还没有报告</EmptyTitle>
                <EmptyDescription>
                  跑完一次分析后，这里会出现决策和分段正文。
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button size="sm" disabled={!canSubmit} onClick={onSubmit}>
                  开始分析
                </Button>
              </EmptyContent>
            </Empty>
          )}
          {reportLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : opened ? (
            <div className="flex flex-col gap-3">
              <FieldDescription className="flex flex-wrap items-center gap-x-2">
                <TickerLink code={opened.code} />
                <span>
                  {opened.name || opened.meta?.name || ""} · {opened.date} ·{" "}
                  {opened.decision || opened.meta?.decision || "—"}
                </span>
              </FieldDescription>
              <Tabs
                value={section}
                onValueChange={(value) => {
                  if (REPORT_SECTIONS.some((item) => item.id === value))
                    onSectionChange(value as ReportSectionId)
                }}
              >
                <TabsList
                  variant="line"
                  className="h-auto w-full flex-wrap justify-start"
                >
                  {REPORT_SECTIONS.map((item) => (
                    <TabsTrigger
                      key={item.id}
                      value={item.id}
                      className="flex-none"
                    >
                      {item.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {REPORT_SECTIONS.map((item) => (
                  <TabsContent key={item.id} value={item.id}>
                    <pre className="text-sm whitespace-pre-wrap">
                      {item.id === section
                        ? openedText || "这一段没有内容。"
                        : ""}
                    </pre>
                  </TabsContent>
                ))}
              </Tabs>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
