import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react"
import { ChartCandlestickIcon, ChevronDownIcon, RefreshCwIcon } from "lucide-react"

import { DailyKChart } from "@/components/daily-k-chart"
import { StockEventsTabs } from "@/components/stock-events-tabs"
import { StockFinancialTab } from "@/components/stock-financial-tab"
import { useJobs } from "@/components/job-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldTitle } from "@/components/ui/field"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { queryStock, submitStockSync, type StockDetail } from "@/lib/api"
import { changeTextClass } from "@/lib/change"
import { notify } from "@/lib/notify"
import { tickerFromCode } from "@/lib/ticker"
import {
  patchUiPrefs,
  readUiPrefs,
  type DetailTabId,
  type InfoSectionId,
} from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

type SlotProps = {
  className?: string
  children?: ReactNode
}

function PanelTitle({ className, children }: SlotProps) {
  return (
    <h2
      className={cn(
        "font-heading text-base leading-none font-medium",
        className
      )}
    >
      {children}
    </h2>
  )
}

function PanelDescription({ className, children }: SlotProps) {
  return (
    <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
  )
}

export function StockDetailPanel({
  code,
  className,
  headerClassName,
  Title = PanelTitle,
  Description = PanelDescription,
}: {
  code: string | null
  className?: string
  headerClassName?: string
  Title?: ComponentType<SlotProps>
  Description?: ComponentType<SlotProps>
}) {
  const { trackJob } = useJobs()
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [newsEpoch, setNewsEpoch] = useState(0)
  const [infoOpen, setInfoOpen] = useState(() => readUiPrefs().infoOpen)
  const [detailTab, setDetailTab] = useState<DetailTabId>(
    () => readUiPrefs().detailTab
  )
  const codeRef = useRef(code)
  codeRef.current = code

  function setInfoSectionOpen(id: InfoSectionId, open: boolean) {
    setInfoOpen((current) => {
      const next = { ...current, [id]: open }
      patchUiPrefs({ infoOpen: next })
      return next
    })
  }

  function setDetailTabPref(next: DetailTabId) {
    setDetailTab(next)
    patchUiPrefs({ detailTab: next })
  }

  function reportError(message: string) {
    notify.error("无法打开股票", { description: message })
  }

  async function loadDetail(target: string) {
    const next = await queryStock(target)
    if (codeRef.current !== target) {
      return
    }
    setDetail(next)
  }

  useEffect(() => {
    if (!code) {
      setDetail(null)
      setLoading(false)
      setRefreshing(false)
      return
    }
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        await loadDetail(code)
      } catch (err: unknown) {
        if (!cancelled) {
          reportError(err instanceof Error ? err.message : "加载失败")
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

  async function refreshCurrent() {
    if (!code) {
      return
    }
    setRefreshing(true)
    try {
      await loadDetail(code)
      if (codeRef.current === code) {
        setNewsEpoch((value) => value + 1)
      }
    } catch (err: unknown) {
      if (codeRef.current === code) {
        reportError(err instanceof Error ? err.message : "刷新失败")
      }
    } finally {
      if (codeRef.current === code) {
        setRefreshing(false)
      }
    }
  }

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
    try {
      const syncingCode = code
      const job = await submitStockSync([syncingCode])
      trackJob(job, {
        onSuccess: async () => {
          if (codeRef.current !== syncingCode) {
            return
          }
          try {
            await loadDetail(syncingCode)
            if (codeRef.current === syncingCode) {
              setNewsEpoch((value) => value + 1)
            }
          } catch (err: unknown) {
            if (codeRef.current === syncingCode) {
              reportError(err instanceof Error ? err.message : "刷新失败")
            }
          }
        },
        onFailure: (done) => {
          if (codeRef.current === syncingCode) {
            reportError(done.error || "同步失败")
          }
        },
      })
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "同步失败")
    } finally {
      setSyncing(false)
    }
  }

  if (!code) {
    return (
      <Empty className={className}>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <ChartCandlestickIcon />
          </EmptyMedia>
          <EmptyTitle>选择股票</EmptyTitle>
          <EmptyDescription>
            点左侧成员，右侧会切换行情、资料、K 线和新闻。
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <div
        className={cn(
          "flex items-start justify-between gap-4",
          headerClassName
        )}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-2 text-left">
          <Title className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="font-mono">{ticker || "股票"}</span>
            {displayName ? (
              <span className="font-sans font-medium">{displayName}</span>
            ) : null}
          </Title>
          <Description>
            {loading && !detail
              ? "加载中…"
              : [
                  profile?.industry,
                  profile?.region,
                  profile?.list_date ? `${profile.list_date} 上市` : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "资料尚未同步"}
          </Description>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
          <div className="flex flex-wrap justify-end gap-1.5">
            <Button
              variant="outline"
              size="sm"
              disabled={syncing || !code}
              onClick={() => void syncCurrent()}
            >
              {syncing ? <Spinner data-icon="inline-start" /> : null}
              同步资料与行情
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={refreshing || loading || !code}
              onClick={() => void refreshCurrent()}
            >
              {refreshing ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <RefreshCwIcon data-icon="inline-start" />
              )}
              刷新
            </Button>
          </div>
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
      {loading && !detail ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-[28rem] w-full" />
        </div>
      ) : detail ? (
        <Tabs
          value={detailTab}
          onValueChange={(value) => setDetailTabPref(value as DetailTabId)}
          className="flex flex-col gap-2.5"
        >
          <TabsList variant="line">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="financials">财报</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="flex flex-col gap-2.5">
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
            <InfoSection
              title="行情"
              open={infoOpen.quotes}
              onOpenChange={(open) => setInfoSectionOpen("quotes", open)}
            >
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
            <InfoSection
              title="估值与股本"
              open={infoOpen.valuation}
              onOpenChange={(open) => setInfoSectionOpen("valuation", open)}
            >
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
            <Separator />
            <DailyKChart
              bars={detail.bars}
              barsWeekly={detail.bars_weekly}
              barsYearly={detail.bars_yearly}
            />
            <Separator />
            {code ? <StockEventsTabs code={code} reloadKey={newsEpoch} /> : null}
          </TabsContent>
          <TabsContent value="financials">
            <StockFinancialTab
              code={code}
              detail={detail}
              onReload={async () => {
                if (!code) {
                  return
                }
                await loadDetail(code)
              }}
              onError={(message) => {
                if (!message) {
                  return
                }
                notify.error("财报操作失败", {
                  description: message,
                  coreHint: false,
                })
              }}
            />
          </TabsContent>
        </Tabs>
      ) : null}
    </div>
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
  open,
  onOpenChange,
  children,
}: {
  title: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible
      className="flex flex-col gap-1"
      open={open}
      onOpenChange={onOpenChange}
    >
      <CollapsibleTrigger className="group/info inline-flex w-fit items-center gap-1 rounded-md text-left font-heading text-sm font-medium tracking-tight text-foreground outline-none hover:opacity-80 focus-visible:ring-[3px] focus-visible:ring-ring/50">
        {title}
        <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-aria-expanded/info:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 pt-1 sm:grid-cols-4 lg:grid-cols-8">
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
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
