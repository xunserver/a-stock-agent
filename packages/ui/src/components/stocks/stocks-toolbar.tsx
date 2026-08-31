import { PlusIcon, RefreshCwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

type StocksToolbarProps = {
  busy: boolean
  selectedCount: number
  onSyncSelected: () => void
  onAdd: () => void
  onRefresh: () => void
}

export function StocksToolbar({
  busy,
  selectedCount,
  onSyncSelected,
  onAdd,
  onRefresh,
}: StocksToolbarProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={busy || selectedCount === 0}
        onClick={onSyncSelected}
      >
        {busy ? <Spinner data-icon="inline-start" /> : null}
        同步所选{selectedCount > 0 ? ` ${selectedCount}` : ""}
      </Button>
      <Button variant="outline" size="sm" disabled={busy} onClick={onAdd}>
        <PlusIcon data-icon="inline-start" />
        加入股票
      </Button>
      <Button variant="outline" size="sm" disabled={busy} onClick={onRefresh}>
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
    </div>
  )
}
