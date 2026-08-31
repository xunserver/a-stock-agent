import { useEffect, useMemo, useState } from "react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
  queryFinancialDetail,
  type FinancialReport,
  type FinancialStatementDetail,
  type FinancialStatementKeyItem,
  type FinancialStatementSheet,
} from "@/lib/api"
import {
  buildStatementRows,
  findPriorPeriodDate,
  fmtPct,
  formatStatementAmount,
  pctClass,
  type StatementRow,
} from "@/lib/financial-statement-rows"
import { previousSameYearPeriodDate } from "@/lib/financial-periods"
import { cn } from "@/lib/utils"

const SHEET_LABELS: Record<FinancialStatementSheet, string> = {
  profit: "利润表",
  balance: "资产负债表",
  cashflow: "现金流量表",
}

const SHEETS = Object.keys(SHEET_LABELS) as FinancialStatementSheet[]

type SheetState = {
  loading: boolean
  error: string | null
  detail: FinancialStatementDetail | null
  priorDetail: FinancialStatementDetail | null
}

function emptySheetState(): SheetState {
  return { loading: false, error: null, detail: null, priorDetail: null }
}

export function StockFinancialStatements({
  code,
  report,
  reports,
  showYoy = false,
  showQoq = false,
}: {
  code: string
  report: FinancialReport | null
  reports: FinancialReport[]
  showYoy?: boolean
  showQoq?: boolean
}) {
  const priorReportDate = useMemo(
    () =>
      report?.report_date
        ? findPriorPeriodDate(report.report_date, reports)
        : null,
    [report?.report_date, reports]
  )

  const priorPriorDate = useMemo(
    () => previousSameYearPeriodDate(priorReportDate),
    [priorReportDate]
  )

  const [sheets, setSheets] = useState<Record<FinancialStatementSheet, SheetState>>(
    () => ({
      profit: emptySheetState(),
      balance: emptySheetState(),
      cashflow: emptySheetState(),
    })
  )

  useEffect(() => {
    if (!code || !report?.report_date) {
      setSheets({
        profit: emptySheetState(),
        balance: emptySheetState(),
        cashflow: emptySheetState(),
      })
      return
    }

    let cancelled = false
    setSheets({
      profit: { loading: true, error: null, detail: null, priorDetail: null },
      balance: { loading: true, error: null, detail: null, priorDetail: null },
      cashflow: { loading: true, error: null, detail: null, priorDetail: null },
    })

    void (async () => {
      const results = await Promise.all(
        SHEETS.map(async (sheet) => {
          try {
            const detail = await queryFinancialDetail(code, {
              sheet,
              reportDate: report.report_date,
            })
            let priorDetail: FinancialStatementDetail | null = null
            if (showQoq && priorReportDate) {
              try {
                priorDetail = await queryFinancialDetail(code, {
                  sheet,
                  reportDate: priorReportDate,
                })
              } catch {
                priorDetail = null
              }
            }
            return {
              sheet,
              state: {
                loading: false,
                error: null,
                detail,
                priorDetail,
              } satisfies SheetState,
            }
          } catch (err: unknown) {
            return {
              sheet,
              state: {
                loading: false,
                error: err instanceof Error ? err.message : "加载失败",
                detail: null,
                priorDetail: null,
              } satisfies SheetState,
            }
          }
        })
      )

      if (cancelled) {
        return
      }

      setSheets((prev) => {
        const next = { ...prev }
        for (const { sheet, state } of results) {
          next[sheet] = state
        }
        return next
      })
    })()

    return () => {
      cancelled = true
    }
  }, [code, report?.report_date, showQoq, priorReportDate])

  // Fetch same-year prior period payloads when needed for incremental QoQ
  const [priorPriorPayloads, setPriorPriorPayloads] = useState<
    Partial<Record<FinancialStatementSheet, Record<string, number | string | null>>>
  >({})

  useEffect(() => {
    if (!code || !priorPriorDate || !showQoq) {
      setPriorPriorPayloads({})
      return
    }

    let cancelled = false
    void (async () => {
      const entries = await Promise.all(
        SHEETS.map(async (sheet) => {
          try {
            const detail = await queryFinancialDetail(code, {
              sheet,
              reportDate: priorPriorDate,
            })
            return [sheet, detail.payload] as const
          } catch {
            return [sheet, null] as const
          }
        })
      )
      if (!cancelled) {
        setPriorPriorPayloads(
          Object.fromEntries(entries.filter(([, payload]) => payload != null))
        )
      }
    })()

    return () => {
      cancelled = true
    }
  }, [code, priorPriorDate, showQoq])

  if (!report) {
    return null
  }

  const showComparisons = showYoy || showQoq

  return (
    <div className="flex flex-col gap-4">
      <p className="font-heading text-sm font-medium tracking-tight text-foreground">
        三大报表
      </p>
      {SHEETS.map((sheet) => (
        <StatementSection
          key={sheet}
          title={SHEET_LABELS[sheet]}
          sheet={sheet}
          reportDate={report.report_date}
          priorReportDate={priorReportDate}
          loading={sheets[sheet].loading}
          error={sheets[sheet].error}
          detail={sheets[sheet].detail}
          priorDetail={sheets[sheet].priorDetail}
          priorPriorPayload={priorPriorPayloads[sheet] ?? null}
          showYoy={showYoy}
          showQoq={showQoq}
          showComparisons={showComparisons}
        />
      ))}
    </div>
  )
}

function StatementSection({
  title,
  sheet,
  reportDate,
  priorReportDate,
  loading,
  error,
  detail,
  priorDetail,
  priorPriorPayload,
  showYoy,
  showQoq,
  showComparisons,
}: {
  title: string
  sheet: FinancialStatementSheet
  reportDate: string
  priorReportDate: string | null
  loading: boolean
  error: string | null
  detail: FinancialStatementDetail | null
  priorDetail: FinancialStatementDetail | null
  priorPriorPayload: Record<string, number | string | null> | null
  showYoy: boolean
  showQoq: boolean
  showComparisons: boolean
}) {
  const rows = useMemo(() => {
    if (!detail) {
      return []
    }
    return buildStatementRows((detail.key_items ?? []) as FinancialStatementKeyItem[], {
      sheet,
      reportDate,
      payload: detail.payload ?? {},
      priorPayload: priorDetail?.payload ?? null,
      priorReportDate,
      priorPriorPayload,
    })
  }, [detail, priorDetail, priorReportDate, priorPriorPayload, reportDate, sheet])

  const filledCount = rows.filter((row) => row.value != null && row.value !== "").length

  return (
    <section className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-[11px] font-medium text-muted-foreground">{title}</h4>
        {!loading && !error && rows.length > 0 ? (
          <p className="text-[11px] text-muted-foreground">
            共 {rows.length} 项，{filledCount} 项有值
          </p>
        ) : null}
      </div>
      <StatementTable
        loading={loading}
        error={error}
        rows={rows}
        showYoy={showYoy}
        showQoq={showQoq}
        showComparisons={showComparisons}
      />
    </section>
  )
}

function StatementTable({
  loading,
  error,
  rows,
  showYoy,
  showQoq,
  showComparisons,
}: {
  loading: boolean
  error: string | null
  rows: StatementRow[]
  showYoy: boolean
  showQoq: boolean
  showComparisons: boolean
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    )
  }
  if (error) {
    return (
      <Empty className="gap-2 border border-dashed p-4">
        <EmptyHeader className="gap-1">
          <EmptyTitle>暂无明细</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  if (!rows.length) {
    return (
      <Empty className="gap-2 border border-dashed p-4">
        <EmptyHeader className="gap-1">
          <EmptyTitle>暂无明细</EmptyTitle>
          <EmptyDescription>请先同步报表明细。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className="rounded-md border border-border px-3 py-2">
      <div className="grid gap-x-8 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map((row) => (
          <StatementRowItem
            key={row.key}
            row={row}
            showYoy={showComparisons && showYoy}
            showQoq={showComparisons && showQoq}
          />
        ))}
      </div>
    </div>
  )
}

function StatementRowItem({
  row,
  showYoy,
  showQoq,
}: {
  row: StatementRow
  showYoy: boolean
  showQoq: boolean
}) {
  const valueText =
    row.kind === "percent"
      ? fmtPct(typeof row.value === "number" ? row.value : null, false)
      : formatStatementAmount(row.value)
  const hasComparisons = showYoy || showQoq

  return (
    <div
      className={cn(
        "min-w-0 py-1",
        row.value == null ? "text-muted-foreground/70" : undefined
      )}
    >
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-sm leading-snug" title={row.label}>
          {row.label}
        </span>
        <span className="text-sm font-medium tabular-nums leading-snug text-foreground">
          {valueText}
        </span>
        {hasComparisons ? (
          <span className="inline-flex flex-wrap items-baseline gap-x-2 text-[11px] leading-4">
            {showYoy ? (
              <span className={cn("tabular-nums", pctClass(row.yoy))}>
                同比{fmtPct(row.yoy)}
              </span>
            ) : null}
            {showQoq ? (
              <span className={cn("tabular-nums", pctClass(row.qoq))}>
                环比{fmtPct(row.qoq)}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
    </div>
  )
}
