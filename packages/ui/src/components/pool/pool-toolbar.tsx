import {
  CloudDownloadIcon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"

type PoolOption = { label: string; value: string }

type PoolToolbarProps = {
  items: PoolOption[]
  poolId: string | null
  busy: boolean
  canDelete: boolean
  hasMembers: boolean
  onSelectPool: (poolId: string | null) => void
  onCreate: () => void
  onAdd: () => void
  onSync: () => void
  onRefresh: () => void
  onDelete: () => void
}

/** Pool-wide actions; state and API calls stay with PoolPage. */
export function PoolToolbar({
  items,
  poolId,
  busy,
  canDelete,
  hasMembers,
  onSelectPool,
  onCreate,
  onAdd,
  onSync,
  onRefresh,
  onDelete,
}: PoolToolbarProps) {
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2">
      <Select
        items={items}
        value={poolId}
        onValueChange={(value) =>
          onSelectPool(typeof value === "string" ? value : null)
        }
      >
        <SelectTrigger className="min-w-56">
          <SelectValue placeholder="选择股票池" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <Button size="sm" onClick={onCreate}>
        <PlusIcon data-icon="inline-start" />
        新建
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!poolId || busy}
        onClick={onAdd}
      >
        <PlusIcon data-icon="inline-start" />
        添加成员
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={!poolId || busy || !hasMembers}
        onClick={onSync}
      >
        {busy ? (
          <Spinner data-icon="inline-start" />
        ) : (
          <CloudDownloadIcon data-icon="inline-start" />
        )}
        同步全部
      </Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={onRefresh}>
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
      <Button
        variant="destructive"
        size="sm"
        disabled={!canDelete || busy}
        onClick={onDelete}
      >
        <Trash2Icon data-icon="inline-start" />
        删除
      </Button>
    </div>
  )
}
