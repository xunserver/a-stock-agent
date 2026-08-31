import { useEffect, useRef, useState, type ComponentType } from "react"
import { ChartCandlestickIcon } from "lucide-react"

import { StockFinancialTab } from "@/components/stock-financial-tab"
import { useJobs } from "@/components/job-provider"
import { DetailHeader } from "@/components/stock-detail/detail-header"
import { OverviewTab } from "@/components/stock-detail/overview-tab"
import {
  PanelDescription,
  PanelTitle,
  type SlotProps,
} from "@/components/stock-detail/panel-slots"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { queryStock, submitStockSync, type StockDetail } from "@/lib/api"
import { notify } from "@/lib/notify"
import { tickerFromCode } from "@/lib/ticker"
import {
  patchUiPrefs,
  readUiPrefs,
  type DetailTabId,
  type InfoSectionId,
} from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

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
  const reportError = (message: string) =>
    notify.error("无法打开股票", { description: message })
  const loadDetail = async (target: string) => {
    const next = await queryStock(target)
    if (codeRef.current === target) setDetail(next)
  }
  const setInfoSectionOpen = (id: InfoSectionId, open: boolean) =>
    setInfoOpen((current) => {
      const next = { ...current, [id]: open }
      patchUiPrefs({ infoOpen: next })
      return next
    })
  const setDetailTabPref = (next: DetailTabId) => {
    setDetailTab(next)
    patchUiPrefs({ detailTab: next })
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
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [code])

  async function refreshCurrent() {
    if (!code) return
    setRefreshing(true)
    try {
      await loadDetail(code)
      if (codeRef.current === code) setNewsEpoch((value) => value + 1)
    } catch (err: unknown) {
      if (codeRef.current === code)
        reportError(err instanceof Error ? err.message : "刷新失败")
    } finally {
      if (codeRef.current === code) setRefreshing(false)
    }
  }

  async function syncCurrent() {
    if (!code) return
    setSyncing(true)
    try {
      const syncingCode = code
      const job = await submitStockSync([syncingCode])
      trackJob(job, {
        onSuccess: async () => {
          if (codeRef.current !== syncingCode) return
          try {
            await loadDetail(syncingCode)
            if (codeRef.current === syncingCode)
              setNewsEpoch((value) => value + 1)
          } catch (err: unknown) {
            if (codeRef.current === syncingCode)
              reportError(err instanceof Error ? err.message : "刷新失败")
          }
        },
        onFailure: (done) => {
          if (codeRef.current === syncingCode)
            reportError(done.error || "同步失败")
        },
      })
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "同步失败")
    } finally {
      setSyncing(false)
    }
  }

  if (!code)
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
  const ticker = detail?.ticker || tickerFromCode(code)
  const profile = detail?.profile
  const quotesAsOf =
    detail?.latest_bar?.trade_date || detail?.quotes_summary?.last || null
  const displayName =
    profile?.name && profile.name !== detail?.code && profile.name !== ticker
      ? profile.name
      : null
  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <DetailHeader
        ticker={ticker}
        displayName={displayName}
        loading={loading}
        detailPresent={Boolean(detail)}
        syncing={syncing}
        refreshing={refreshing}
        quotesAsOf={quotesAsOf}
        profileUpdatedAt={profile?.updated_at}
        className={headerClassName}
        Title={Title}
        Description={Description}
        onSync={() => void syncCurrent()}
        onRefresh={() => void refreshCurrent()}
        description={
          loading && !detail
            ? "加载中…"
            : [
                profile?.industry,
                profile?.region,
                profile?.list_date ? `${profile.list_date} 上市` : null,
              ]
                .filter(Boolean)
                .join(" · ") || "资料尚未同步"
        }
      />
      {loading && !detail ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-[28rem] w-full" />
        </div>
      ) : null}
      {detail ? (
        <Tabs
          value={detailTab}
          onValueChange={(value) => setDetailTabPref(value as DetailTabId)}
          className="flex flex-col gap-2.5"
        >
          <TabsList variant="line">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="financials">财报</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <OverviewTab
              code={code}
              detail={detail}
              infoOpen={infoOpen}
              onInfoOpenChange={setInfoSectionOpen}
              newsEpoch={newsEpoch}
            />
          </TabsContent>
          <TabsContent value="financials">
            <StockFinancialTab
              code={code}
              detail={detail}
              onReload={() => loadDetail(code)}
              onError={(message) => {
                if (message)
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
