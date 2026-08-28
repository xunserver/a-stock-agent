import { useEffect, useMemo, useState } from "react"
import {
  CalendarDaysIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleAlertIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  queryCalendarGrid,
  queryCalendarOverview,
  type CalendarGrid,
  type CalendarGridMarket,
  type CalendarOverviewMarket,
} from "@/lib/api"
import { monthGrid, shiftMonth, weekdayLabel, WEEKDAY_LABELS } from "@/lib/month-grid"
import { cn } from "@/lib/utils"

function timezoneLabel(tz: string) {
  if (tz === "Asia/Shanghai") return "北京时间"
  if (tz === "America/New_York") return "美东时间"
  return tz
}

function badgeVariant(
  marketId: string
): "default" | "secondary" | "outline" {
  if (marketId === "cn_a") return "default"
  if (marketId === "us") return "secondary"
  return "outline"
}

function DaySessions({
  date,
  grid,
}: {
  date: string
  grid: CalendarGrid
}) {
  const openIds = new Set(
    grid.days.find((item) => item.date === date)?.markets ?? []
  )
  const openMarkets = grid.markets.filter((market) => openIds.has(market.id))

  if (openMarkets.length === 0) {
    return (
      <p className="text-muted-foreground text-xs">
        {date} {weekdayLabel(date)} · 已接入市场当日休市
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium">
        {date} {weekdayLabel(date)}
      </p>
      {openMarkets.map((market) => (
        <MarketSessions key={market.id} date={date} market={market} />
      ))}
    </div>
  )
}

function MarketSessions({
  date,
  market,
}: {
  date: string
  market: CalendarGridMarket
}) {
  const live = date === market.today && market.in_session
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border p-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Badge variant={badgeVariant(market.id)}>{market.badge}</Badge>
          <span className="font-medium">{market.title}</span>
        </div>
        <Badge variant={live ? "default" : "secondary"}>
          {live ? "交易中" : "开市"}
        </Badge>
      </div>
      <p className="text-muted-foreground text-[11px]">
        {timezoneLabel(market.timezone)}
      </p>
      {market.sessions.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {market.sessions.map((session) => (
            <li
              key={`${session.label}-${session.start}`}
              className="flex items-center justify-between gap-2 text-xs"
            >
              <span className="text-muted-foreground">{session.label}</span>
              <span className="font-mono tabular-nums">
                {session.start}–{session.end}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {market.sessions_note ? (
        <p className="text-muted-foreground text-[11px] leading-snug">
          {market.sessions_note}
        </p>
      ) : null}
    </div>
  )
}

export function MarketCalendarButton() {
  const [open, setOpen] = useState(false)
  const [overview, setOverview] = useState<CalendarOverviewMarket[] | null>(
    null
  )
  const [grid, setGrid] = useState<CalendarGrid | null>(null)
  const [year, setYear] = useState(() => new Date().getFullYear())
  const [month, setMonth] = useState(() => new Date().getMonth() + 1)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const payload = await queryCalendarOverview()
        if (!cancelled) setOverview(payload.markets)
      } catch {
        // 顶栏图标提示可失败；点开后再报错。
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        const payload = await queryCalendarGrid({ year, month })
        if (cancelled) return
        setGrid(payload)
        setSelected((prev) => {
          if (prev && prev.startsWith(`${payload.year}-${String(payload.month).padStart(2, "0")}`)) {
            return prev
          }
          if (
            payload.today.startsWith(
              `${payload.year}-${String(payload.month).padStart(2, "0")}`
            )
          ) {
            return payload.today
          }
          return payload.days[0]?.date ?? null
        })
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, year, month])

  const cells = useMemo(() => monthGrid(year, month), [year, month])
  const marketsById = useMemo(() => {
    const map = new Map<string, CalendarGridMarket>()
    for (const market of grid?.markets ?? []) {
      map.set(market.id, market)
    }
    return map
  }, [grid])
  const tradingByDate = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const day of grid?.days ?? []) {
      map.set(day.date, day.markets)
    }
    return map
  }, [grid])

  const cnA = overview?.find((item) => item.id === "cn_a")
  const headerHint =
    cnA == null
      ? null
      : !cnA.has_calendar
        ? "无日历"
        : cnA.today_is_trading
          ? cnA.in_session
            ? "A股交易中"
            : "A股开市"
          : "A股休市"

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="交易日历"
            title={headerHint ?? "交易日历"}
            className={cn(headerHint?.includes("交易中") && "text-primary")}
          />
        }
      >
        <CalendarDaysIcon />
        <span className="sr-only">交易日历</span>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        side="bottom"
        sideOffset={8}
        className="w-[min(26rem,calc(100vw-2rem))] gap-3 p-3"
      >
        <PopoverHeader>
          <div className="flex items-center justify-between gap-2">
            <PopoverTitle>交易日历</PopoverTitle>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="上个月"
                onClick={() => {
                  const next = shiftMonth(year, month, -1)
                  setYear(next.year)
                  setMonth(next.month)
                }}
              >
                <ChevronLeftIcon />
              </Button>
              <span className="min-w-24 text-center text-sm tabular-nums">
                {year}年{month}月
              </span>
              <Button
                variant="ghost"
                size="icon-xs"
                aria-label="下个月"
                onClick={() => {
                  const next = shiftMonth(year, month, 1)
                  setYear(next.year)
                  setMonth(next.month)
                }}
              >
                <ChevronRightIcon />
              </Button>
            </div>
          </div>
        </PopoverHeader>
        {error ? (
          <div className="text-destructive flex items-start gap-2 text-xs">
            <CircleAlertIcon className="mt-0.5" />
            <span>{error}</span>
          </div>
        ) : null}
        {loading && grid == null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-7 gap-1">
              {WEEKDAY_LABELS.map((label) => (
                <div
                  key={label}
                  className="text-muted-foreground text-center text-[11px]"
                >
                  {label}
                </div>
              ))}
              {cells.map((cell) => {
                const openMarkets = tradingByDate.get(cell.date) ?? []
                const isSelected = cell.date === selected
                const isToday = cell.date === grid?.today
                return (
                  <button
                    key={cell.date}
                    type="button"
                    disabled={!cell.inMonth}
                    onClick={() => setSelected(cell.date)}
                    className={cn(
                      "flex min-h-12 flex-col items-center gap-0.5 rounded-md px-0.5 py-1 text-xs outline-none",
                      cell.inMonth
                        ? "hover:bg-muted"
                        : "text-muted-foreground/40",
                      isSelected && "bg-muted ring-1 ring-foreground/15",
                      isToday && !isSelected && "text-primary"
                    )}
                  >
                    <span
                      className={cn(
                        "tabular-nums",
                        isToday && "font-medium"
                      )}
                    >
                      {cell.day}
                    </span>
                    {cell.inMonth && openMarkets.length > 0 ? (
                      <span className="flex max-w-full flex-wrap justify-center gap-0.5">
                        {openMarkets.map((id) => {
                          const market = marketsById.get(id)
                          if (!market) return null
                          return (
                            <Badge
                              key={id}
                              variant={badgeVariant(id)}
                              className="h-3.5 min-w-3.5 px-0.5 text-[9px] leading-none"
                            >
                              {market.badge}
                            </Badge>
                          )
                        })}
                      </span>
                    ) : (
                      <span className="h-3.5" />
                    )}
                  </button>
                )
              })}
            </div>
            {grid && selected ? (
              <DaySessions date={selected} grid={grid} />
            ) : null}
          </div>
        )}
        <Separator />
        <div className="flex flex-col gap-1.5">
          <PopoverDescription>
            格子上的徽章表示当天开市的市场；点一天看交易时段。
          </PopoverDescription>
          {grid && grid.markets.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {grid.markets.map((market) => (
                <Badge key={market.id} variant={badgeVariant(market.id)}>
                  {market.badge} {market.title}
                </Badge>
              ))}
            </div>
          ) : null}
          {grid?.markets.some((market) => !market.has_calendar) ? (
            <p className="text-muted-foreground text-[11px]">
              {grid.markets
                .filter((market) => !market.has_calendar)
                .map((market) => market.title)
                .join("、")}
              日历尚未同步，开市日暂不标记。
            </p>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  )
}
