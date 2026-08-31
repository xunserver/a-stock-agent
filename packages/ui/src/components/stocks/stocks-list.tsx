import { LandmarkIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { TickerLink } from "@/components/ticker-link"
import type { StockRow } from "@/lib/api"
import { tickerFromCode } from "@/lib/ticker"

type StocksListProps = {
  stocks: StockRow[] | null
  loading: boolean
  busy: boolean
  selected: Set<string>
  allSelected: boolean
  someSelected: boolean
  onToggleOne: (code: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  onSync: (codes: string[]) => void
  onRemove: (code: string) => void
  onAdd: (mode: "codes" | "index") => void
}

function stockId(stock: Pick<StockRow, "code" | "ticker">) {
  return stock.ticker || tickerFromCode(stock.code)
}

function poolLabel(stock: StockRow) {
  if (stock.pools.length === 0) return "未入池，可以从系统移除"
  return `在 ${stock.pools.map((pool) => pool.name || pool.id).join("、")} 中，无法从系统移除`
}

export function StocksList({
  stocks,
  loading,
  busy,
  selected,
  allSelected,
  someSelected,
  onToggleOne,
  onToggleAll,
  onSync,
  onRemove,
  onAdd,
}: StocksListProps) {
  if (loading && stocks === null) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    )
  }
  if (!stocks || stocks.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LandmarkIcon />
          </EmptyMedia>
          <EmptyTitle>还没有股票</EmptyTitle>
          <EmptyDescription>
            先按代码或指数加入系统，再去股票池里挑选成员。移除不会删已入库的日线。
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <div className="flex flex-wrap justify-center gap-2">
            <Button size="sm" disabled={busy} onClick={() => onAdd("codes")}>
              添加代码
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => onAdd("index")}
            >
              按指数添加
            </Button>
          </div>
        </EmptyContent>
      </Empty>
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8">
            <Checkbox
              aria-label="全选"
              checked={allSelected}
              indeterminate={someSelected}
              disabled={busy}
              onCheckedChange={onToggleAll}
            />
          </TableHead>
          <TableHead>股票</TableHead>
          <TableHead>行业</TableHead>
          <TableHead>最新 K</TableHead>
          <TableHead className="w-28">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {stocks.map((stock) => {
          const blocked = stock.pools.length > 0
          const checked = selected.has(stock.code)
          return (
            <TableRow
              key={stock.code}
              data-state={checked ? "selected" : undefined}
            >
              <TableCell>
                <Checkbox
                  aria-label={`选择 ${stockId(stock)}`}
                  checked={checked}
                  disabled={busy}
                  onCheckedChange={(next) =>
                    onToggleOne(stock.code, next === true)
                  }
                />
              </TableCell>
              <TableCell>
                <TickerLink
                  code={stock.code}
                  className="inline-flex items-baseline gap-2"
                >
                  <span className="font-mono">{stockId(stock)}</span>
                  {stock.name ? (
                    <span className="font-sans">{stock.name}</span>
                  ) : null}
                </TickerLink>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {stock.industry || "—"}
              </TableCell>
              <TableCell className="font-mono text-muted-foreground">
                {stock.last_bar || "—"}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={busy}
                    onClick={() => onSync([stock.code])}
                  >
                    同步
                  </Button>
                  {blocked ? (
                    <Tooltip>
                      <TooltipTrigger render={<span className="inline-flex" />}>
                        <Button variant="ghost" size="xs" disabled>
                          移除
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{poolLabel(stock)}</TooltipContent>
                    </Tooltip>
                  ) : (
                    <Button
                      variant="ghost"
                      size="xs"
                      disabled={busy}
                      onClick={() => onRemove(stock.code)}
                    >
                      移除
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
