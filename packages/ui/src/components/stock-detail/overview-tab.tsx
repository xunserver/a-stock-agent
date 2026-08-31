import { DailyKChart } from "@/components/daily-k-chart"
import { StockEventsTabs } from "@/components/stock-events-tabs"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import type { StockDetail } from "@/lib/api"
import { changeTextClass } from "@/lib/change"
import type { InfoSectionId } from "@/lib/ui-prefs"

import { fmtNum, fmtPct, fmtPrice, fmtRatio } from "./formatters"
import { InfoField, InfoSection } from "./info-section"

type Props = {
  code: string
  detail: StockDetail
  infoOpen: Record<InfoSectionId, boolean>
  onInfoOpenChange: (id: InfoSectionId, open: boolean) => void
  newsEpoch: number
}

export function OverviewTab({
  code,
  detail,
  infoOpen,
  onInfoOpenChange,
  newsEpoch,
}: Props) {
  const { profile, latest_bar: latest } = detail
  return (
    <div className="flex flex-col gap-2.5">
      {profile?.is_st || profile?.is_suspended ? (
        <div className="flex flex-wrap items-center gap-2">
          {profile?.is_st ? <Badge variant="destructive">ST</Badge> : null}
          {profile?.is_suspended ? (
            <Badge variant="secondary">停牌 {profile.suspend_info || ""}</Badge>
          ) : null}
        </div>
      ) : null}
      <InfoSection
        title="行情"
        open={infoOpen.quotes}
        onOpenChange={(open) => onInfoOpenChange("quotes", open)}
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
            latest?.turnover != null ? `${fmtPrice(latest.turnover)}%` : "—"
          }
        />
        <InfoField title="量比" value={fmtRatio(profile?.volume_ratio)} />
        <InfoField title="外盘" value={fmtNum(profile?.outer_vol)} />
        <InfoField title="内盘" value={fmtNum(profile?.inner_vol)} />
      </InfoSection>
      <InfoSection
        title="估值与股本"
        open={infoOpen.valuation}
        onOpenChange={(open) => onInfoOpenChange("valuation", open)}
      >
        <InfoField title="市盈率(动)" value={fmtRatio(profile?.pe_dyn)} />
        <InfoField title="市盈率(静)" value={fmtRatio(profile?.pe_static)} />
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
      <StockEventsTabs code={code} reloadKey={newsEpoch} />
    </div>
  )
}
