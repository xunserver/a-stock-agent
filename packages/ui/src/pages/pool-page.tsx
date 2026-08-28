import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link } from "react-router"
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronsUpIcon,
  CloudDownloadIcon,
  FolderIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react"

import { useJobs } from "@/components/job-provider"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { StockDetailPanel } from "@/components/stock-detail-panel"
import {
  addPoolCodes,
  addPoolIndex,
  createPool,
  deletePool,
  queryPoolList,
  queryPools,
  querySettings,
  queryStatus,
  removePoolCodes,
  reorderPoolMembers,
  submitQuotesSync,
  type PoolMember,
  type PoolSummary,
  type Status,
} from "@/lib/api"
import { INDEX_OPTIONS } from "@/lib/indexes"
import { withQueuedHint } from "@/lib/jobs"
import { notify } from "@/lib/notify"
import {
  activeMemberCodes,
  moveMemberDown,
  moveMemberToFirst,
  moveMemberUp,
} from "@/lib/member-order"
import { filterMembersByQuery } from "@/lib/member-query"
import {
  filterMembersByQuotePlan,
  nextQuoteFilter,
  type QuoteFilter,
} from "@/lib/quote-filter"
import { tickerFromCode } from "@/lib/ticker"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

const QUOTE_FILTERS: {
  value: QuoteFilter
  label: string
  count: (status: Status | null) => number | undefined
}[] = [
  {
    value: "all",
    label: "全部",
    count: (status) => status?.pool_active,
  },
  {
    value: "sync",
    label: "需同步",
    count: (status) =>
      status?.need_sync ??
      (status?.need_full ?? 0) + (status?.need_fill ?? 0),
  },
]

export function PoolPage() {
  const { trackJob, jobs } = useJobs()
  const [pools, setPools] = useState<PoolSummary[]>([])
  const [poolId, setPoolId] = useState<string | null>(
    () => readUiPrefs().poolId
  )
  const [status, setStatus] = useState<Status | null>(null)
  const [members, setMembers] = useState<PoolMember[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [createId, setCreateId] = useState("")
  const [createName, setCreateName] = useState("")

  const [deleteOpen, setDeleteOpen] = useState(false)

  const [addOpen, setAddOpen] = useState(false)
  const [addMode, setAddMode] = useState<"codes" | "index">("codes")
  const [addCodes, setAddCodes] = useState("")
  const [addIndex, setAddIndex] = useState("hs300")
  const [replaceIndex, setReplaceIndex] = useState(false)

  const [removeCodes, setRemoveCodes] = useState<string[] | null>(null)
  const [editing, setEditing] = useState(false)
  const [checkedCodes, setCheckedCodes] = useState<Set<string>>(() => new Set())
  const [pickedCode, setPickedCode] = useState<string | null>(
    () => readUiPrefs().pickedCode
  )
  const [quoteFilter, setQuoteFilter] = useState<QuoteFilter>(
    () => readUiPrefs().quoteFilter
  )
  const [memberQuery, setMemberQuery] = useState("")

  const poolItems = useMemo(
    () =>
      pools.map((pool) => ({
        label: `${pool.name} · ${pool.id}`,
        value: pool.id,
      })),
    [pools]
  )
  const canDelete = pools.length > 1 && poolId !== null
  const quotedMembers = useMemo(
    () => filterMembersByQuotePlan(members, quoteFilter),
    [members, quoteFilter]
  )
  const visibleMembers = useMemo(
    () => filterMembersByQuery(quotedMembers, memberQuery),
    [quotedMembers, memberQuery]
  )
  const selectedCode = useMemo(() => {
    if (!members || members.length === 0) {
      return null
    }
    const pickedInPool = Boolean(
      pickedCode && members.some((member) => member.code === pickedCode)
    )
    if (quotedMembers && quotedMembers.length > 0) {
      if (
        pickedCode &&
        quotedMembers.some((member) => member.code === pickedCode)
      ) {
        return pickedCode
      }
      return quotedMembers[0].code
    }
    return pickedInPool ? pickedCode : members[0].code
  }, [members, pickedCode, quotedMembers])
  const visibleActiveCodes = useMemo(
    () =>
      (visibleMembers ?? [])
        .filter((member) => member.status === "active")
        .map((member) => member.code),
    [visibleMembers]
  )
  const fullActiveCodes = useMemo(
    () => activeMemberCodes(members),
    [members]
  )
  const checkedCount = checkedCodes.size
  const allVisibleChecked = Boolean(
    visibleActiveCodes.length > 0 &&
      visibleActiveCodes.every((code) => checkedCodes.has(code))
  )
  const someVisibleChecked =
    visibleActiveCodes.some((code) => checkedCodes.has(code)) &&
    !allVisibleChecked
  const showDetailPane =
    (loading && members === null) || Boolean(members && members.length > 0)

  async function loadAll(preferred?: string) {
    const [listing, settings] = await Promise.all([
      queryPools(),
      querySettings(),
    ])
    const preferredId = preferred ?? poolId ?? settings.pool
    const nextId =
      listing.pools.find((pool) => pool.id === preferredId)?.id ??
      listing.pools[0]?.id ??
      null
    setPools(listing.pools)
    setPoolId(nextId)
    if (nextId) {
      patchUiPrefs({ poolId: nextId })
    }
    if (!nextId) {
      setStatus(null)
      setMembers([])
      setCheckedCodes(new Set())
      setEditing(false)
      return
    }
    const [nextStatus, membersListing] = await Promise.all([
      queryStatus(nextId),
      queryPoolList(nextId),
    ])
    setStatus(nextStatus)
    setMembers(membersListing.members)
    const codes = new Set(membersListing.members.map((member) => member.code))
    setCheckedCodes(
      (prev) => new Set([...prev].filter((code) => codes.has(code)))
    )
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await loadAll()
      } catch (err: unknown) {
        if (!cancelled) {
          notify.error("股票池操作失败", {
            description: err instanceof Error ? err.message : "加载失败",
          })
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // First paint only; later reloads go through loadAll with an explicit pool.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
    } catch (err: unknown) {
      notify.error("股票池操作失败", {
        description: err instanceof Error ? err.message : "操作失败",
      })
    } finally {
      setBusy(false)
      setLoading(false)
    }
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = createId.trim()
    if (!id) {
      return
    }
    await run(async () => {
      await createPool(id, createName.trim() || id)
      setCreateOpen(false)
      setCreateId("")
      setCreateName("")
      notify.success(`已创建股票池 ${id}`)
      await loadAll(id)
    })
  }

  async function onSyncAll() {
    if (!poolId) {
      return
    }
    const currentPoolId = poolId
    await run(async () => {
      const job = await submitQuotesSync(currentPoolId)
      trackJob(job, {
        onSuccess: async () => {
          notify.success("已同步当前池行情")
          await loadAll(currentPoolId)
        },
        onFailure: (done) =>
          notify.error("股票池操作失败", {
            description: done.error || "同步失败",
          }),
      })
      notify.success(withQueuedHint("已提交同步全部任务", jobs, job))
    })
  }

  async function onDelete() {
    if (!poolId) {
      return
    }
    const deleting = poolId
    await run(async () => {
      await deletePool(deleting)
      setDeleteOpen(false)
      notify.success(`已删除股票池 ${deleting}`)
      await loadAll()
    })
  }

  async function onAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!poolId) {
      return
    }
    await run(async () => {
      if (addMode === "codes") {
        await addPoolCodes(poolId, addCodes)
        notify.success("已按代码加入成分")
        await loadAll(poolId)
      } else {
        const currentPoolId = poolId
        const index = addIndex
        const replacing = replaceIndex
        const job = await addPoolIndex(currentPoolId, index, replacing)
        trackJob(job, {
          onSuccess: async () => {
            notify.success(
              replacing ? `已用 ${index} 覆盖当前池` : `已并入 ${index}`
            )
            await loadAll(currentPoolId)
          },
          onFailure: (done) =>
            notify.error("股票池操作失败", {
              description: done.error || "按指数添加失败",
            }),
        })
        notify.success(withQueuedHint(`已提交 ${index} 成分任务`, jobs, job))
      }
      setAddOpen(false)
      setAddCodes("")
      setReplaceIndex(false)
    })
  }

  async function onRemove(codes: string[]) {
    if (!poolId || codes.length === 0) {
      return
    }
    await run(async () => {
      await removePoolCodes(poolId, codes)
      setRemoveCodes(null)
      setCheckedCodes((prev) => {
        const next = new Set(prev)
        for (const code of codes) {
          next.delete(code)
        }
        return next
      })
      const label =
        codes.length === 1 ? tickerFromCode(codes[0]) : `${codes.length} 只`
      notify.success(`已移出 ${label}`)
      await loadAll(poolId)
    })
  }

  async function onReorder(nextCodes: string[] | null) {
    if (!poolId || !nextCodes) {
      return
    }
    const current = activeMemberCodes(members)
    if (
      current.length === nextCodes.length &&
      current.every((code, index) => code === nextCodes[index])
    ) {
      return
    }
    await run(async () => {
      await reorderPoolMembers(poolId, nextCodes)
      await loadAll(poolId)
    })
  }

  function toggleOne(code: string, checked: boolean) {
    setCheckedCodes((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(code)
      } else {
        next.delete(code)
      }
      return next
    })
  }

  function toggleAll(checked: boolean) {
    setCheckedCodes((prev) => {
      const next = new Set(prev)
      if (checked) {
        for (const code of visibleActiveCodes) {
          next.add(code)
        }
      } else {
        for (const code of visibleActiveCodes) {
          next.delete(code)
        }
      }
      return next
    })
  }

  async function onSelectPool(next: string | null) {
    if (!next || next === poolId) {
      return
    }
    setPoolId(next)
    setQuoteFilter("all")
    setMemberQuery("")
    setCheckedCodes(new Set())
    setEditing(false)
    patchUiPrefs({ poolId: next, quoteFilter: "all" })
    setLoading(true)
    await run(async () => {
      await loadAll(next)
    })
  }

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100dvh-5.25rem)]">
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <Select
          items={poolItems}
          value={poolId}
          onValueChange={(value) => {
            void onSelectPool(typeof value === "string" ? value : null)
          }}
        >
          <SelectTrigger className="min-w-56">
            <SelectValue placeholder="选择股票池" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {poolItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <PlusIcon data-icon="inline-start" />
          新建
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!poolId || busy}
          onClick={() => {
            setAddMode("codes")
            setAddOpen(true)
          }}
        >
          <PlusIcon data-icon="inline-start" />
          添加成员
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!poolId || busy || !members || members.length === 0}
          onClick={() => void onSyncAll()}
        >
          {busy ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <CloudDownloadIcon data-icon="inline-start" />
          )}
          同步全部
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={() => {
            setLoading(true)
            void run(async () => {
              await loadAll(poolId ?? undefined)
            })
          }}
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
        <Button
          variant="destructive"
          size="sm"
          disabled={!canDelete || busy}
          onClick={() => setDeleteOpen(true)}
        >
          <Trash2Icon data-icon="inline-start" />
          删除
        </Button>
      </div>

      <div
        className={cn(
          "grid min-h-0 flex-1 gap-4",
          showDetailPane && "lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)]"
        )}
      >
        <Card className="h-full max-h-80 min-h-0 lg:max-h-none">
          <CardHeader className="border-b">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <ToggleGroup
              aria-label="按行情状态筛选"
              value={[quoteFilter]}
              onValueChange={(next) => {
                const value = nextQuoteFilter(next, quoteFilter)
                if (value) {
                  setQuoteFilter(value)
                  patchUiPrefs({ quoteFilter: value })
                }
              }}
              variant="outline"
              size="sm"
              spacing={0}
              className="shrink-0"
            >
              {QUOTE_FILTERS.map((item) => {
                const count = item.count(status)
                return (
                  <ToggleGroupItem
                    key={item.value}
                    value={item.value}
                    onPressedChange={(pressed) => {
                      if (pressed) {
                        setQuoteFilter(item.value)
                      }
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
              onChange={(event) => setMemberQuery(event.target.value)}
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
                onClick={() => setRemoveCodes([...checkedCodes])}
              >
                移出所选{checkedCount > 0 ? ` ${checkedCount}` : ""}
              </Button>
            ) : null}
            <Button
              variant={editing ? "secondary" : "outline"}
              size="sm"
              className="shrink-0"
              disabled={busy || !members || members.length === 0}
              onClick={() => {
                if (editing) {
                  setEditing(false)
                  setCheckedCodes(new Set())
                  return
                }
                setEditing(true)
              }}
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
          <CardContent className="min-h-0 flex-1 overflow-auto">
            {loading && members === null ? (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : members && members.length > 0 ? (
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
                          onCheckedChange={(checked) =>
                            toggleAll(checked === true)
                          }
                        />
                      </TableHead>
                    ) : null}
                    <TableHead>股票</TableHead>
                    {editing ? (
                      <TableHead className="w-[7.5rem]">操作</TableHead>
                    ) : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleMembers && visibleMembers.length > 0 ? (
                    visibleMembers.map((member) => {
                      const selected = member.code === selectedCode
                      const checked = checkedCodes.has(member.code)
                      const canRemove = member.status === "active"
                      const visibleIndex = visibleActiveCodes.indexOf(
                        member.code
                      )
                      const canUp = canRemove && visibleIndex > 0
                      const canDown =
                        canRemove &&
                        visibleIndex >= 0 &&
                        visibleIndex < visibleActiveCodes.length - 1
                      const canToFirst = canUp
                      return (
                        <TableRow
                          key={member.code}
                          data-state={selected ? "selected" : undefined}
                          aria-selected={selected}
                          tabIndex={0}
                          className="cursor-pointer"
                          onClick={() => {
                            setPickedCode(member.code)
                            patchUiPrefs({ pickedCode: member.code })
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault()
                              setPickedCode(member.code)
                              patchUiPrefs({ pickedCode: member.code })
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
                                  toggleOne(member.code, next === true)
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
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    disabled={busy || !canUp}
                                    aria-label="上移"
                                    title="上移"
                                    onClick={() =>
                                      void onReorder(
                                        moveMemberUp(
                                          fullActiveCodes,
                                          visibleActiveCodes,
                                          member.code
                                        )
                                      )
                                    }
                                  >
                                    <ArrowUpIcon />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    disabled={busy || !canDown}
                                    aria-label="下移"
                                    title="下移"
                                    onClick={() =>
                                      void onReorder(
                                        moveMemberDown(
                                          fullActiveCodes,
                                          visibleActiveCodes,
                                          member.code
                                        )
                                      )
                                    }
                                  >
                                    <ArrowDownIcon />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    disabled={busy || !canToFirst}
                                    aria-label="置顶"
                                    title="移到首位"
                                    onClick={() =>
                                      void onReorder(
                                        moveMemberToFirst(
                                          fullActiveCodes,
                                          visibleActiveCodes,
                                          member.code
                                        )
                                      )
                                    }
                                  >
                                    <ChevronsUpIcon />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    disabled={busy}
                                    aria-label="删除"
                                    title="删除"
                                    onClick={() =>
                                      setRemoveCodes([member.code])
                                    }
                                  >
                                    <Trash2Icon />
                                  </Button>
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
            ) : (
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <FolderIcon />
                  </EmptyMedia>
                  <EmptyTitle>股票池是空的</EmptyTitle>
                  <EmptyDescription>
                    成员必须先在「股票」里。可以按代码加入，或按指数并入系统里已有的成分。移出不会删已入库的日线。
                  </EmptyDescription>
                </EmptyHeader>
                <EmptyContent>
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button size="sm" render={<Link to="/stocks" />}>
                      去股票管理
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!poolId || busy}
                      onClick={() => {
                        setAddMode("codes")
                        setAddOpen(true)
                      }}
                    >
                      添加代码
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!poolId || busy}
                      onClick={() => {
                        setAddMode("index")
                        setAddOpen(true)
                      }}
                    >
                      按指数添加
                    </Button>
                  </div>
                </EmptyContent>
              </Empty>
            )}
          </CardContent>
        </Card>

        {showDetailPane ? (
          <Card className="h-full min-h-0 min-w-0">
            <CardContent className="min-h-0 flex-1 overflow-y-auto">
              {loading && members === null ? (
                <div className="flex flex-col gap-2">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-[28rem] w-full" />
                </div>
              ) : (
                <StockDetailPanel code={selectedCode} />
              )}
            </CardContent>
          </Card>
        ) : null}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => void onCreate(event)}
          >
            <DialogHeader>
              <DialogTitle>新建股票池</DialogTitle>
              <DialogDescription>
                id 给命令用，名称显示在列表里。不会改系统设置里的默认池。
              </DialogDescription>
            </DialogHeader>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="new-pool-id">id</FieldLabel>
                <Input
                  id="new-pool-id"
                  name="pool_id"
                  required
                  value={createId}
                  placeholder="hs300"
                  onChange={(event) => setCreateId(event.target.value)}
                />
                <FieldDescription>
                  字母、数字、下划线或短横线，最长 32 位。
                </FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="new-pool-name">名称</FieldLabel>
                <Input
                  id="new-pool-name"
                  name="name"
                  value={createName}
                  placeholder="沪深300样本"
                  onChange={(event) => setCreateName(event.target.value)}
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type="submit" disabled={busy}>
                {busy ? <Spinner data-icon="inline-start" /> : null}
                创建
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => void onAdd(event)}
          >
            <DialogHeader>
              <DialogTitle>添加成员</DialogTitle>
              <DialogDescription>
                只能加入已经在「股票」里的代码。按指数加入时，只并入系统里已有的成分。指数拉取可能要几秒。
              </DialogDescription>
            </DialogHeader>
            <FieldGroup>
              <Field>
                <FieldTitle id="add-mode-label">方式</FieldTitle>
                <ToggleGroup
                  aria-labelledby="add-mode-label"
                  value={[addMode]}
                  onValueChange={(next) => {
                    const mode = next[0]
                    if (mode === "codes" || mode === "index") {
                      setAddMode(mode)
                    }
                  }}
                  variant="outline"
                  spacing={0}
                >
                  <ToggleGroupItem value="codes">代码</ToggleGroupItem>
                  <ToggleGroupItem value="index">指数</ToggleGroupItem>
                </ToggleGroup>
              </Field>
              {addMode === "codes" ? (
                <Field>
                  <FieldLabel htmlFor="add-codes">股票代码</FieldLabel>
                  <Textarea
                    id="add-codes"
                    required
                    value={addCodes}
                    placeholder="000001, 600519"
                    onChange={(event) => setAddCodes(event.target.value)}
                  />
                  <FieldDescription>
                    逗号或换行分隔，6 位代码。不在系统里的代码会拒绝。
                  </FieldDescription>
                </Field>
              ) : (
                <>
                  <Field>
                    <FieldTitle id="add-index-label">指数</FieldTitle>
                    <ToggleGroup
                      aria-labelledby="add-index-label"
                      value={[addIndex]}
                      onValueChange={(next) => {
                        if (next[0]) {
                          setAddIndex(next[0])
                        }
                      }}
                      variant="outline"
                      className="w-full max-w-full flex-wrap"
                    >
                      {INDEX_OPTIONS.map((option) => (
                        <ToggleGroupItem
                          key={option.value}
                          value={option.value}
                        >
                          {option.label}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </Field>
                  <Field orientation="horizontal">
                    <FieldContent>
                      <FieldLabel htmlFor="replace-index">
                        覆盖当前成分
                      </FieldLabel>
                      <FieldDescription>
                        打开后，不在指数里的票会标为移除，行情仍保留。
                      </FieldDescription>
                    </FieldContent>
                    <Switch
                      id="replace-index"
                      checked={replaceIndex}
                      onCheckedChange={setReplaceIndex}
                    />
                  </Field>
                </>
              )}
            </FieldGroup>
            <DialogFooter>
              <Button type="submit" disabled={busy || !poolId}>
                {busy ? <Spinner data-icon="inline-start" /> : null}
                {addMode === "index" ? "拉取并加入" : "加入"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除股票池 {poolId}？</AlertDialogTitle>
            <AlertDialogDescription>
              只删池和成员关系，已入库的日线还在。至少保留一个股票池。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={busy}
              onClick={(event) => {
                event.preventDefault()
                void onDelete()
              }}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={removeCodes !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRemoveCodes(null)
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {removeCodes && removeCodes.length === 1
                ? `移出 ${tickerFromCode(removeCodes[0])}？`
                : `移出 ${removeCodes?.length ?? 0} 只股票？`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              从当前池拿掉
              {removeCodes && removeCodes.length === 1 ? "这只票" : "这些票"}
              ，不删日线。以后还可以再加回来。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy || !removeCodes || removeCodes.length === 0}
              onClick={(event) => {
                event.preventDefault()
                if (removeCodes && removeCodes.length > 0) {
                  void onRemove(removeCodes)
                }
              }}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              移出
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
