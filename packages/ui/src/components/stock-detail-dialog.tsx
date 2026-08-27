import { useEffect, useRef, useState, type ReactNode } from "react"
import { CircleAlertIcon } from "lucide-react"

import { DailyKChart } from "@/components/daily-k-chart"
import { useJobs } from "@/components/job-provider"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldTitle } from "@/components/ui/field"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { queryStock, submitStockSync, type StockDetail } from "@/lib/api"
import { changeTextClass } from "@/lib/change"
import { tickerFromCode } from "@/lib/ticker"
import { cn } from "@/lib/utils"

export function StockDetailDialog({
  code,
  onOpenChange,
}: {
  code: string | null
  onOpenChange: (open: boolean) => void
}) {
  const { trackJob } = useJobs()
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const codeRef = useRef(code)
  codeRef.current = code

  useEffect(() => {
    if (!code) {
      setDetail(null)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        const next = await queryStock(code)
        if (!cancelled) {
          setDetail(next)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败")
          setDetail(null)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [code])

  const ticker = detail?.ticker || (code ? tickerFromCode(code) : "")
  const profile = detail?.profile
  const latest = detail?.latest_bar
  const summary = detail?.quotes_summary
  const quotesAsOf = latest?.trade_date || summary?.last || null
  const profileUpdatedAt = fmtTimestamp(profile?.updated_at)
  const displayName =
    profile?.name && profile.name !== detail?.code && profile.name !== ticker
      ? profile.name
      : null

  async function syncCurrent() {
    if (!code) {
      return
    }
    setSyncing(true)
    setError(null)
    try {
      const syncingCode = code
      const job = await submitStockSync([syncingCode])
      trackJob(job, {
        onSuccess: async () => {
          const next = await queryStock(syncingCode)
          if (codeRef.current === syncingCode) setDetail(next)
        },
        onFailure: (done) => {
          if (codeRef.current === syncingCode)
            setError(done.error || "同步失败")
        },
      })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "同步失败")
    } finally {
      setSyncing(false)
    }
  }

  return (
    <Dialog open={code !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] min-w-0 overflow-x-hidden overflow-y-auto sm:max-w-6xl">
        <div className="flex items-start justify-between gap-4 pr-8">
          <DialogHeader className="min-w-0 flex-1 text-left">
            <DialogTitle className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="font-mono">{ticker || "股票"}</span>
              {displayName ? (
                <span className="font-sans font-medium">{displayName}</span>
              ) : null}
            </DialogTitle>
            <DialogDescription>
              {loading && !detail
                ? "加载中…"
                : [
                    profile?.industry,
                    profile?.region,
                    profile?.list_date ? `${profile.list_date} 上市` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "资料尚未同步"}
            </DialogDescription>
          </DialogHeader>
          <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
            <Button
              variant="outline"
              size="sm"
              disabled={syncing || !code}
              onClick={() => void syncCurrent()}
            >
              {syncing ? <Spinner data-icon="inline-start" /> : null}
              同步资料与行情
            </Button>
            {detail || !loading ? (
              <p className="text-right text-[11px] leading-4 whitespace-nowrap text-muted-foreground">
                {[
                  quotesAsOf ? `行情至 ${quotesAsOf}` : "尚无日线",
                  profileUpdatedAt
                    ? `资料更新 ${profileUpdatedAt}`
                    : "资料未同步",
                ].join(" · ")}
              </p>
            ) : null}
          </div>
        </div>
        {error ? (
          <Alert variant="destructive">
            <CircleAlertIcon />
            <AlertTitle>无法打开股票</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {loading && !detail ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-[28rem] w-full" />
          </div>
        ) : detail ? (
          <div className="flex flex-col gap-2.5">
            {profile?.is_st || profile?.is_suspended ? (
              <div className="flex flex-wrap items-center gap-2">
                {profile?.is_st ? (
                  <Badge variant="destructive">ST</Badge>
                ) : null}
                {profile?.is_suspended ? (
                  <Badge variant="secondary">
                    停牌 {profile.suspend_info || ""}
                  </Badge>
                ) : null}
              </div>
            ) : null}
            <InfoSection title="行情">
              <InfoField
                title="最新价"
                value={fmtPrice(profile?.latest_price ?? latest?.close)}
                className={changeTextClass(latest?.pct_chg)}
              />
              <InfoField
                title="涨跌幅"
                value={fmtPct(latest?.pct_chg)}
                className={changeTextClass(latest?.pct_chg)}
              />
              <InfoField
                title="涨跌额"
                value={fmtPrice(latest?.change_amount ?? null)}
                className={changeTextClass(latest?.change_amount)}
              />
              <InfoField title="今开" value={fmtPrice(latest?.open)} />
              <InfoField title="最高" value={fmtPrice(latest?.high)} />
              <InfoField title="最低" value={fmtPrice(latest?.low)} />
              <InfoField title="昨收" value={fmtPrice(profile?.pre_close)} />
              <InfoField title="均价" value={fmtPrice(profile?.avg_price)} />
              <InfoField title="涨停" value={fmtPrice(profile?.high_limit)} />
              <InfoField title="跌停" value={fmtPrice(profile?.low_limit)} />
              <InfoField title="成交量" value={fmtNum(latest?.volume)} />
              <InfoField title="成交额" value={fmtNum(latest?.amount)} />
              <InfoField
                title="换手率"
                value={
                  latest?.turnover != null
                    ? `${fmtPrice(latest.turnover)}%`
                    : "—"
                }
              />
              <InfoField title="量比" value={fmtRatio(profile?.volume_ratio)} />
              <InfoField title="外盘" value={fmtNum(profile?.outer_vol)} />
              <InfoField title="内盘" value={fmtNum(profile?.inner_vol)} />
            </InfoSection>
            <InfoSection title="估值与股本">
              <InfoField title="市盈率(动)" value={fmtRatio(profile?.pe_dyn)} />
              <InfoField
                title="市盈率(静)"
                value={fmtRatio(profile?.pe_static)}
              />
              <InfoField title="市净率" value={fmtRatio(profile?.pb)} />
              <InfoField title="总市值" value={fmtNum(profile?.total_mv)} />
              <InfoField title="流通市值" value={fmtNum(profile?.float_mv)} />
              <InfoField title="总股本" value={fmtNum(profile?.total_shares)} />
              <InfoField title="流通股" value={fmtNum(profile?.float_shares)} />
              <InfoField title="每股收益" value={fmtRatio(profile?.eps)} />
              <InfoField title="每股净资产" value={fmtRatio(profile?.bps)} />
            </InfoSection>
            <InfoSection title="财务">
              <InfoField title="ROE" value={fmtPct(profile?.roe, false)} />
              <InfoField title="营收" value={fmtNum(profile?.revenue)} />
              <InfoField
                title="营收同比"
                value={fmtPct(profile?.revenue_yoy)}
              />
              <InfoField
                title="净利润同比"
                value={fmtPct(profile?.net_profit_yoy ?? profile?.net_profit)}
              />
              <InfoField
                title="毛利率"
                value={fmtPct(profile?.gross_margin, false)}
              />
              <InfoField
                title="净利率"
                value={fmtPct(profile?.net_margin, false)}
              />
              <InfoField
                title="资产负债率"
                value={fmtPct(profile?.debt_ratio, false)}
              />
            </InfoSection>
            <Separator />
            <DailyKChart
              bars={detail.bars}
              barsWeekly={detail.bars_weekly}
              barsYearly={detail.bars_yearly}
            />
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function fmtTimestamp(value: string | null | undefined): string | null {
  if (!value) {
    return null
  }
  return value.replace("T", " ").replace(/\.\d+/, "")
}

function fmtPrice(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  return value.toFixed(2)
}

function fmtPct(value: number | null | undefined, signed = true): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  const sign = signed && value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  if (Math.abs(value) >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`
  }
  if (Math.abs(value) >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`
  }
  return value.toFixed(2)
}

function fmtRatio(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "—"
  }
  return value.toFixed(2)
}

function InfoSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[11px] font-medium text-muted-foreground">{title}</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-4 lg:grid-cols-8">
        {children}
      </div>
    </div>
  )
}

function InfoField({
  title,
  value,
  className,
}: {
  title: string
  value: string
  className?: string
}) {
  return (
    <Field className="flex-row flex-wrap items-baseline gap-1 *:w-auto max-sm:flex-col max-sm:items-start">
      <FieldTitle className="text-[11px] font-normal text-muted-foreground">
        {title}
      </FieldTitle>
      <FieldDescription
        className={cn("mt-0 text-xs leading-4 text-foreground", className)}
      >
        {value}
      </FieldDescription>
    </Field>
  )
}
