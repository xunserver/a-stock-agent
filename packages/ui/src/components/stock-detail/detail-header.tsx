import type { ComponentType, ReactNode } from "react"
import { RefreshCwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { fmtTimestamp } from "./formatters"
import { cn } from "@/lib/utils"

type SlotProps = { className?: string; children?: ReactNode }

export function DetailHeader({
  ticker,
  displayName,
  description,
  loading,
  detailPresent,
  syncing,
  refreshing,
  quotesAsOf,
  profileUpdatedAt,
  className,
  Title,
  Description,
  onSync,
  onRefresh,
}: {
  ticker: string
  displayName: string | null
  description: string
  loading: boolean
  detailPresent: boolean
  syncing: boolean
  refreshing: boolean
  quotesAsOf: string | null
  profileUpdatedAt: string | null | undefined
  className?: string
  Title: ComponentType<SlotProps>
  Description: ComponentType<SlotProps>
  onSync: () => void
  onRefresh: () => void
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-2 text-left">
        <Title className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="font-mono">{ticker || "股票"}</span>
          {displayName ? (
            <span className="font-sans font-medium">{displayName}</span>
          ) : null}
        </Title>
        <Description>{description}</Description>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
        <div className="flex flex-wrap justify-end gap-1.5">
          <Button
            variant="outline"
            size="sm"
            disabled={syncing}
            onClick={onSync}
          >
            {syncing ? <Spinner data-icon="inline-start" /> : null}
            同步资料与行情
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={refreshing || loading}
            onClick={onRefresh}
          >
            {refreshing ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <RefreshCwIcon data-icon="inline-start" />
            )}
            刷新
          </Button>
        </div>
        {detailPresent || !loading ? (
          <p className="text-right text-[11px] leading-4 whitespace-nowrap text-muted-foreground">
            {[
              quotesAsOf ? `行情至 ${quotesAsOf}` : "尚无日线",
              profileUpdatedAt
                ? `资料更新 ${fmtTimestamp(profileUpdatedAt)}`
                : "资料未同步",
            ].join(" · ")}
          </p>
        ) : null}
      </div>
    </div>
  )
}
