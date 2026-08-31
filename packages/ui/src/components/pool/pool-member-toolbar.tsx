import { CheckIcon, PencilIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Status } from "@/lib/api"
import { nextQuoteFilter, type QuoteFilter } from "@/lib/quote-filter"

const FILTERS: {
  value: QuoteFilter
  label: string
  count: (status: Status | null) => number | undefined
}[] = [
  { value: "all", label: "全部", count: (status) => status?.pool_active },
  {
    value: "sync",
    label: "需同步",
    count: (status) =>
      status?.need_sync ?? (status?.need_full ?? 0) + (status?.need_fill ?? 0),
  },
]

type PoolMemberToolbarProps = {
  status: Status | null
  loading: boolean
  quoteFilter: QuoteFilter
  memberQuery: string
  editing: boolean
  checkedCount: number
  busy: boolean
  hasMembers: boolean
  onQuoteFilterChange: (filter: QuoteFilter) => void
  onMemberQueryChange: (query: string) => void
  onRemoveSelected: () => void
  onEditingChange: (editing: boolean) => void
}

export function PoolMemberToolbar(props: PoolMemberToolbarProps) {
  const {
    status,
    loading,
    quoteFilter,
    memberQuery,
    editing,
    checkedCount,
    busy,
    hasMembers,
    onQuoteFilterChange,
    onMemberQueryChange,
    onRemoveSelected,
    onEditingChange,
  } = props
  return (
    <CardHeader className="border-b">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <ToggleGroup
          aria-label="按行情状态筛选"
          value={[quoteFilter]}
          onValueChange={(next) => {
            const filter = nextQuoteFilter(next, quoteFilter)
            if (filter) onQuoteFilterChange(filter)
          }}
          variant="outline"
          size="sm"
          spacing={0}
          className="shrink-0"
        >
          {FILTERS.map((item) => {
            const count = item.count(status)
            return (
              <ToggleGroupItem
                key={item.value}
                value={item.value}
                onPressedChange={(pressed) => {
                  if (pressed) onQuoteFilterChange(item.value)
                }}
              >
                {item.label}
                <span className="tabular-nums">
                  {loading && count === undefined ? "—" : (count ?? "—")}
                </span>
              </ToggleGroupItem>
            )
          })}
        </ToggleGroup>
        <Input
          id="pool-member-query"
          value={memberQuery}
          onChange={(event) => onMemberQueryChange(event.target.value)}
          placeholder="代码或名称"
          autoComplete="off"
          aria-label="按代码或名称快速查询"
          className="h-7 min-w-0 flex-1"
        />
        {editing ? (
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            disabled={busy || checkedCount === 0}
            onClick={onRemoveSelected}
          >
            移出所选{checkedCount > 0 ? ` ${checkedCount}` : ""}
          </Button>
        ) : null}
        <Button
          variant={editing ? "secondary" : "outline"}
          size="sm"
          className="shrink-0"
          disabled={busy || !hasMembers}
          onClick={() => onEditingChange(!editing)}
        >
          {editing ? (
            <CheckIcon data-icon="inline-start" />
          ) : (
            <PencilIcon data-icon="inline-start" />
          )}
          {editing ? "完成" : "编辑"}
        </Button>
      </div>
    </CardHeader>
  )
}
