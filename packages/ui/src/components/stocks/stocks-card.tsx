import type { StockRow } from "@/lib/api"

import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

import { StocksList } from "./stocks-list"
import { StocksToolbar } from "./stocks-toolbar"

type StocksCardProps = {
  stocks: StockRow[] | null
  loading: boolean
  busy: boolean
  selected: Set<string>
  selectedCount: number
  allSelected: boolean
  someSelected: boolean
  onSync: (codes: string[]) => void
  onToggleOne: (code: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  onRemove: (code: string) => void
  onAdd: (mode: "codes" | "index") => void
  onRefresh: () => void
}

export function StocksCard({
  stocks,
  loading,
  busy,
  selected,
  selectedCount,
  allSelected,
  someSelected,
  onSync,
  onToggleOne,
  onToggleAll,
  onRemove,
  onAdd,
  onRefresh,
}: StocksCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>股票</CardTitle>
        <CardAction>
          <StocksToolbar
            busy={busy}
            selectedCount={selectedCount}
            onSyncSelected={() => onSync([...selected])}
            onAdd={() => onAdd("codes")}
            onRefresh={onRefresh}
          />
        </CardAction>
      </CardHeader>
      <CardContent>
        <StocksList
          stocks={stocks}
          loading={loading}
          busy={busy}
          selected={selected}
          allSelected={allSelected}
          someSelected={someSelected}
          onToggleOne={onToggleOne}
          onToggleAll={onToggleAll}
          onSync={onSync}
          onRemove={onRemove}
          onAdd={onAdd}
        />
      </CardContent>
    </Card>
  )
}
