import { useEffect, useMemo, useState } from "react"

import { StockFinancialStatements } from "@/components/stock-financial-statements"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldTitle } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { FinancialReport } from "@/lib/api"
import {
  buildComparisons,
  emptyComparisons,
  FINANCIAL_METRICS,
  formatMetricValue,
  formatReportPeriod,
  fmtPct,
  pctClass,
  type MetricConfig,
} from "@/lib/financial-metrics"
import { cn } from "@/lib/utils"

export function StockFinancialReport({
  code,
  reports,
  className,
}: {
  code: string
  reports: FinancialReport[]
  className?: string
}) {
  const [selectedDate, setSelectedDate] = useState<string | null>(
    reports[0]?.report_date ?? null
  )
  const [showYoy, setShowYoy] = useState(false)
  const [showQoq, setShowQoq] = useState(false)

  const periodItems = useMemo(
    () =>
      reports
        .filter((report) => report.report_date)
        .map((report) => ({
          value: report.report_date,
          label: formatReportPeriod(report),
        })),
    [reports]
  )

  useEffect(() => {
    if (!reports.length) {
      setSelectedDate(null)
      return
    }
    if (
      !selectedDate ||
      !reports.some((report) => report.report_date === selectedDate)
    ) {
      setSelectedDate(reports[0].report_date)
    }
  }, [reports, selectedDate])

  const comparisons = useMemo(() => buildComparisons(reports), [reports])
  const selectedReport =
    reports.find((report) => report.report_date === selectedDate) ?? null
  const selectedComparisons = selectedDate
    ? (comparisons.get(selectedDate) ?? emptyComparisons())
    : emptyComparisons()

  if (!reports.length) {
    return (
      <div className={cn("flex flex-col gap-1.5", className)}>
        <Empty className="gap-2 border border-dashed p-4">
          <EmptyHeader className="gap-1">
            <EmptyTitle>暂无财报数据</EmptyTitle>
            <EmptyDescription>请先同步资料与行情。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    )
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium text-muted-foreground">
            报告期
          </span>
          <Select
            items={periodItems}
            value={selectedDate}
            onValueChange={(value) => {
              if (typeof value === "string") {
                setSelectedDate(value)
              }
            }}
          >
            <SelectTrigger className="min-w-32">
              <SelectValue placeholder="选择报告期" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {periodItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          {selectedReport?.notice_date ? (
            <span className="text-[11px] text-muted-foreground">
              公告日 {selectedReport.notice_date}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={showYoy}
              onCheckedChange={(checked) => setShowYoy(checked === true)}
            />
            同比
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={showQoq}
              onCheckedChange={(checked) => setShowQoq(checked === true)}
            />
            环比
          </label>
        </div>
      </div>

      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        {FINANCIAL_METRICS.map((metric) => (
          <MetricField
            key={metric.key}
            metric={metric}
            value={selectedReport?.[metric.key]}
            comparisons={selectedComparisons[metric.key]}
            showYoy={showYoy}
            showQoq={showQoq}
          />
        ))}
      </div>

      <StockFinancialStatements
        code={code}
        report={selectedReport}
        reports={reports}
        showYoy={showYoy}
        showQoq={showQoq}
      />
    </div>
  )
}

function MetricField({
  metric,
  value,
  comparisons,
  showYoy,
  showQoq,
}: {
  metric: MetricConfig
  value: number | null | undefined
  comparisons: { yoy: number | null; qoq: number | null }
  showYoy: boolean
  showQoq: boolean
}) {
  const showComparisons = showYoy || showQoq

  return (
    <Field className="gap-1">
      <FieldTitle className="text-[11px] font-normal text-muted-foreground">
        {metric.label}
      </FieldTitle>
      <FieldDescription className="mt-0 flex flex-col gap-0.5">
        <span className="text-sm font-medium tabular-nums text-foreground">
          {formatMetricValue(metric, value)}
        </span>
        {showComparisons ? (
          <span className="flex flex-wrap gap-x-2 text-[11px] leading-4">
            {showYoy ? (
              <span className={cn("tabular-nums", pctClass(comparisons.yoy))}>
                同比{fmtPct(comparisons.yoy)}
              </span>
            ) : null}
            {showQoq ? (
              <span className={cn("tabular-nums", pctClass(comparisons.qoq))}>
                环比{fmtPct(comparisons.qoq)}
              </span>
            ) : null}
          </span>
        ) : null}
      </FieldDescription>
    </Field>
  )
}
