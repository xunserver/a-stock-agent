import { Button } from "@/components/ui/button"
import { Toggle } from "@/components/ui/toggle"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { changeTextClass } from "@/lib/change"
import type { ChartPalette } from "@/lib/chart-theme"
import { cn } from "@/lib/utils"

import {
  INDICATORS,
  PERIODS,
  RANGE_PRESETS,
  fmtNum,
  fmtPct,
  fmtPrice,
  type Candle,
  type ChartLineOverlay,
  type PeriodId,
} from "./daily-k-chart-model"

export function ChartPeriodPicker({
  periodId,
  onSelect,
}: {
  periodId: PeriodId
  onSelect: (period: PeriodId) => void
}) {
  return (
    <ToggleGroup
      value={[periodId]}
      onValueChange={(next) => {
        const id = next[0]
        if (id === "daily" || id === "weekly" || id === "yearly") onSelect(id)
      }}
      variant="outline"
      size="sm"
      spacing={0}
    >
      {PERIODS.map((item) => (
        <ToggleGroupItem key={item.id} value={item.id}>
          {item.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

export function ChartToolbar({
  periodId,
  onSelectPeriod,
  canZoomIn,
  canZoomOut,
  onApplyRange,
  onZoom,
}: {
  periodId: PeriodId
  onSelectPeriod: (period: PeriodId) => void
  canZoomIn: boolean
  canZoomOut: boolean
  onApplyRange: (days: number) => void
  onZoom: (factor: number) => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <ChartPeriodPicker periodId={periodId} onSelect={onSelectPeriod} />
      <div className="flex flex-wrap items-center justify-end gap-1">
        {RANGE_PRESETS.map((preset) => (
          <Button
            key={preset.id}
            type="button"
            variant="outline"
            size="xs"
            onClick={() => onApplyRange(preset.days)}
          >
            {preset.label}
          </Button>
        ))}
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={!canZoomOut}
          onClick={() => onZoom(1.35)}
        >
          缩小
        </Button>
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={!canZoomIn}
          onClick={() => onZoom(0.7)}
        >
          放大
        </Button>
      </div>
    </div>
  )
}

export function IndicatorLegend({
  active,
  palette,
  indicatorIds,
  overlays,
  onToggle,
}: {
  active: Candle
  palette: ChartPalette | null
  indicatorIds: string[]
  overlays: ChartLineOverlay[]
  onToggle: (id: string, pressed: boolean) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {INDICATORS.map((item) => {
        const overlay = overlays.find((row) => row.id === item.id)
        const point = overlay?.data.find(
          (row) => row.time === active.trade_date
        )
        const pressed = indicatorIds.includes(item.id)
        const swatch =
          item.kind === "close" && palette ? palette.foreground : item.color
        return (
          <Toggle
            key={item.id}
            size="sm"
            variant="outline"
            pressed={pressed}
            onPressedChange={(next) => onToggle(item.id, next)}
            aria-label={`${item.label}${pressed ? " 显示中" : " 已隐藏"}`}
            className={cn(!pressed && "opacity-45")}
          >
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: swatch }}
            />
            <span>{item.label}</span>
            <span
              className="font-normal tabular-nums"
              style={{ color: swatch }}
            >
              {fmtPrice(point?.value)}
            </span>
          </Toggle>
        )
      })}
    </div>
  )
}

export function QuoteStats({ active }: { active: Candle }) {
  const yang = (active.close ?? 0) >= (active.open ?? 0)
  const change = active.pct_chg ?? (yang ? 1 : -1)
  return (
    <div className="rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
      <div className="grid w-full grid-cols-[7.25rem_4.25rem_3.25rem_repeat(8,minmax(0,1fr))] items-baseline gap-x-2 text-xs leading-4">
        <span className="font-medium tabular-nums">{active.trade_date}</span>
        <span
          className={cn(
            "font-medium tabular-nums",
            changeTextClass(active.pct_chg)
          )}
        >
          {fmtPct(active.pct_chg)}
        </span>
        <span className={cn("tabular-nums", changeTextClass(active.pct_chg))}>
          {active.change_amount != null ? fmtPrice(active.change_amount) : "—"}
        </span>
        <QuoteStat
          label="开"
          value={fmtPrice(active.open)}
          className={changeTextClass(change)}
        />
        <QuoteStat
          label="高"
          value={fmtPrice(active.high)}
          className={changeTextClass(change)}
        />
        <QuoteStat
          label="低"
          value={fmtPrice(active.low)}
          className={changeTextClass(change)}
        />
        <QuoteStat
          label="收"
          value={fmtPrice(active.close)}
          className={changeTextClass(change)}
        />
        <QuoteStat label="量" value={fmtNum(active.volume)} />
        <QuoteStat label="额" value={fmtNum(active.amount)} />
        <QuoteStat
          label="换手"
          value={
            active.turnover != null ? `${fmtPrice(active.turnover)}%` : "—"
          }
        />
        <QuoteStat
          label="振幅"
          value={
            active.amplitude != null ? `${fmtPrice(active.amplitude)}%` : "—"
          }
        />
      </div>
    </div>
  )
}

function QuoteStat({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <span className="inline-flex min-w-0 items-baseline gap-1">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className={cn("min-w-0 truncate tabular-nums", className)}>
        {value}
      </span>
    </span>
  )
}
