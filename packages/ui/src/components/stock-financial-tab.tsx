import { useRef, useState } from "react"

import { useJobs } from "@/components/job-provider"
import { StockFinancialReport } from "@/components/stock-financial-report"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import {
  submitStockSync,
  type FinancialReport,
  type StockDetail,
} from "@/lib/api"

export function StockFinancialTab({
  code,
  detail,
  onReload,
  onError,
}: {
  code: string
  detail: StockDetail
  onReload: () => Promise<void>
  onError: (message: string | null) => void
}) {
  const { trackJob } = useJobs()
  const [syncingStatements, setSyncingStatements] = useState(false)
  const codeRef = useRef(code)
  codeRef.current = code

  const summary = detail.financial_summary
  const latestReport = detail.financial_reports?.[0]
  const summaryText = formatSummary(summary, latestReport)

  async function syncStatements() {
    setSyncingStatements(true)
    onError(null)
    try {
      const syncingCode = code
      const job = await submitStockSync([syncingCode], { withStatements: true })
      trackJob(job, {
        onSuccess: async () => {
          if (codeRef.current !== syncingCode) {
            return
          }
          try {
            await onReload()
          } catch (err: unknown) {
            if (codeRef.current === syncingCode) {
              onError(err instanceof Error ? err.message : "刷新失败")
            }
          }
        },
        onFailure: (done) => {
          if (codeRef.current === syncingCode) {
            onError(done.error || "报表明细同步失败")
          }
        },
      })
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : "报表明细同步失败")
    } finally {
      setSyncingStatements(false)
    }
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] text-muted-foreground">{summaryText}</p>
        <Button
          variant="outline"
          size="sm"
          disabled={syncingStatements}
          onClick={() => void syncStatements()}
        >
          {syncingStatements ? <Spinner data-icon="inline-start" /> : null}
          同步报表明细
        </Button>
      </div>
      <StockFinancialReport
        code={code}
        reports={detail.financial_reports ?? []}
      />
    </div>
  )
}

function formatSummary(
  summary: StockDetail["financial_summary"],
  latestReport: FinancialReport | undefined
): string {
  if (!summary?.count) {
    return "暂无财报数据，请先同步资料与行情"
  }
  const latestLabel =
    latestReport?.report_type ||
    latestReport?.report_date ||
    summary.latest_report_date
  if (latestLabel) {
    return `共 ${summary.count} 期，最新 ${latestLabel}`
  }
  return `共 ${summary.count} 期`
}
