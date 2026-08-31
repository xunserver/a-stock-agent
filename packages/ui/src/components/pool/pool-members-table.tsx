import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronsUpIcon,
  Trash2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { PoolMember } from "@/lib/api"
import { tickerFromCode } from "@/lib/ticker"

type PoolMembersTableProps = {
  members: PoolMember[]
  selectedCode: string | null
  editing: boolean
  busy: boolean
  checkedCodes: Set<string>
  visibleActiveCodes: string[]
  allVisibleChecked: boolean
  someVisibleChecked: boolean
  memberQuery: string
  onSelect: (code: string) => void
  onToggleOne: (code: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  onMoveUp: (code: string) => void
  onMoveDown: (code: string) => void
  onMoveToFirst: (code: string) => void
  onRemove: (codes: string[]) => void
}

export function PoolMembersTable({
  members,
  selectedCode,
  editing,
  busy,
  checkedCodes,
  visibleActiveCodes,
  allVisibleChecked,
  someVisibleChecked,
  memberQuery,
  onSelect,
  onToggleOne,
  onToggleAll,
  onMoveUp,
  onMoveDown,
  onMoveToFirst,
  onRemove,
}: PoolMembersTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {editing ? (
            <TableHead className="w-8">
              <Checkbox
                aria-label="全选当前列表"
                checked={allVisibleChecked}
                indeterminate={someVisibleChecked}
                disabled={busy || visibleActiveCodes.length === 0}
                onCheckedChange={(checked) => onToggleAll(checked === true)}
              />
            </TableHead>
          ) : null}
          <TableHead>股票</TableHead>
          {editing ? <TableHead className="w-[7.5rem]">操作</TableHead> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.length > 0 ? (
          members.map((member) => {
            const selected = member.code === selectedCode
            const checked = checkedCodes.has(member.code)
            const canRemove = member.status === "active"
            const visibleIndex = visibleActiveCodes.indexOf(member.code)
            const canUp = canRemove && visibleIndex > 0
            const canDown =
              canRemove &&
              visibleIndex >= 0 &&
              visibleIndex < visibleActiveCodes.length - 1
            return (
              <TableRow
                key={member.code}
                data-state={selected ? "selected" : undefined}
                aria-selected={selected}
                tabIndex={0}
                className="cursor-pointer"
                onClick={() => onSelect(member.code)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onSelect(member.code)
                  }
                }}
              >
                {editing ? (
                  <TableCell
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    <Checkbox
                      aria-label={`选择 ${tickerFromCode(member.code)}`}
                      checked={checked}
                      disabled={busy || !canRemove}
                      onCheckedChange={(next) =>
                        onToggleOne(member.code, next === true)
                      }
                    />
                  </TableCell>
                ) : null}
                <TableCell>
                  <span className="inline-flex items-baseline gap-2">
                    <span className="font-mono">
                      {tickerFromCode(member.code)}
                    </span>
                    {member.name ? (
                      <span className="font-sans">{member.name}</span>
                    ) : null}
                  </span>
                </TableCell>
                {editing ? (
                  <TableCell
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    {canRemove ? (
                      <div className="flex items-center">
                        <MemberAction
                          icon={<ArrowUpIcon />}
                          label="上移"
                          disabled={busy || !canUp}
                          onClick={() => onMoveUp(member.code)}
                        />
                        <MemberAction
                          icon={<ArrowDownIcon />}
                          label="下移"
                          disabled={busy || !canDown}
                          onClick={() => onMoveDown(member.code)}
                        />
                        <MemberAction
                          icon={<ChevronsUpIcon />}
                          label="置顶"
                          title="移到首位"
                          disabled={busy || !canUp}
                          onClick={() => onMoveToFirst(member.code)}
                        />
                        <MemberAction
                          icon={<Trash2Icon />}
                          label="删除"
                          disabled={busy}
                          onClick={() => onRemove([member.code])}
                        />
                      </div>
                    ) : null}
                  </TableCell>
                ) : null}
              </TableRow>
            )
          })
        ) : (
          <TableRow>
            <TableCell
              colSpan={editing ? 3 : 1}
              className="text-muted-foreground"
            >
              {memberQuery.trim() ? "无匹配" : "空"}
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
}

function MemberAction({
  icon,
  label,
  title,
  disabled,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  title?: string
  disabled: boolean
  onClick: () => void
}) {
  return (
    <Button
      variant="ghost"
      size="icon-xs"
      disabled={disabled}
      aria-label={label}
      title={title ?? label}
      onClick={onClick}
    >
      {icon}
    </Button>
  )
}
