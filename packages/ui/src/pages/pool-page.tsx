import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link } from "react-router"
import {
  CircleAlertIcon,
  FolderIcon,
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import { TickerLink } from "@/components/ticker-link"
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
  type PoolMember,
  type PoolSummary,
  type Status,
} from "@/lib/api"
import { INDEX_OPTIONS } from "@/lib/indexes"
import { withQueuedHint } from "@/lib/jobs"
import { tickerFromCode } from "@/lib/ticker"

function memberStatusLabel(status: string) {
  if (status === "active") return "在池"
  if (status === "removed") return "已移除"
  return status
}

export function PoolPage() {
  const { trackJob, jobs } = useJobs()
  const [pools, setPools] = useState<PoolSummary[]>([])
  const [poolId, setPoolId] = useState<string | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [members, setMembers] = useState<PoolMember[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
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

  const [removeCode, setRemoveCode] = useState<string | null>(null)

  const poolItems = useMemo(
    () =>
      pools.map((pool) => ({
        label: `${pool.name} · ${pool.id}`,
        value: pool.id,
      })),
    [pools]
  )
  const currentPool = pools.find((pool) => pool.id === poolId) ?? null
  const canDelete = pools.length > 1 && poolId !== null

  async function loadAll(preferred?: string) {
    setError(null)
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
    if (!nextId) {
      setStatus(null)
      setMembers([])
      return
    }
    const [nextStatus, membersListing] = await Promise.all([
      queryStatus(nextId),
      queryPoolList(nextId),
    ])
    setStatus(nextStatus)
    setMembers(membersListing.members)
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await loadAll()
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败")
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
    setError(null)
    setNotice(null)
    try {
      await action()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "操作失败")
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
      setNotice(`已创建股票池 ${id}`)
      await loadAll(id)
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
      setNotice(`已删除股票池 ${deleting}`)
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
        setNotice("已按代码加入成分")
        await loadAll(poolId)
      } else {
        const currentPoolId = poolId
        const index = addIndex
        const replacing = replaceIndex
        const job = await addPoolIndex(currentPoolId, index, replacing)
        trackJob(job, {
          onSuccess: async () => {
            setNotice(
              replacing ? `已用 ${index} 覆盖当前池` : `已并入 ${index}`
            )
            await loadAll(currentPoolId)
          },
          onFailure: (done) => setError(done.error || "按指数添加失败"),
        })
        setNotice(withQueuedHint(`已提交 ${index} 成分任务`, jobs, job))
      }
      setAddOpen(false)
      setAddCodes("")
      setReplaceIndex(false)
    })
  }

  async function onRemove(code: string) {
    if (!poolId) {
      return
    }
    await run(async () => {
      await removePoolCodes(poolId, [code])
      setRemoveCode(null)
      setNotice(`已移出 ${code}`)
      await loadAll(poolId)
    })
  }

  async function onSelectPool(next: string | null) {
    if (!next || next === poolId) {
      return
    }
    setPoolId(next)
    setLoading(true)
    await run(async () => {
      await loadAll(next)
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>股票池操作失败</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}
      {notice && !error ? (
        <Alert>
          <AlertTitle>已更新</AlertTitle>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
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
        <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>
          <PlusIcon data-icon="inline-start" />
          新建
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!canDelete || busy}
          onClick={() => setDeleteOpen(true)}
        >
          <Trash2Icon data-icon="inline-start" />
          删除
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="在池" value={status?.pool_active} loading={loading} />
        <Stat label="需全历史" value={status?.need_full} loading={loading} />
        <Stat label="需补缺口" value={status?.need_fill} loading={loading} />
        <Stat label="已齐" value={status?.already_current} loading={loading} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>成员</CardTitle>
          <CardDescription>
            {status
              ? `${currentPool?.name ?? status.pool} · ${members?.length ?? 0} 只活跃 · 资料 ${status.profile_filled} / ${status.pool_active}`
              : "从 core 读取当前池"}
          </CardDescription>
          <CardAction>
            <div className="flex flex-wrap gap-2">
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
            </div>
          </CardAction>
        </CardHeader>
        <CardContent>
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
                  <TableHead>股票</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>最新 K</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead className="w-20">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow key={member.code}>
                    <TableCell>
                      <TickerLink
                        code={member.code}
                        className="inline-flex items-baseline gap-2"
                      >
                        <span className="font-mono">
                          {tickerFromCode(member.code)}
                        </span>
                        {member.name ? (
                          <span className="font-sans">{member.name}</span>
                        ) : null}
                      </TickerLink>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          member.status === "active" ? "secondary" : "outline"
                        }
                      >
                        {memberStatusLabel(member.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-muted-foreground">
                      {member.last_bar || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {member.source || "—"}
                    </TableCell>
                    <TableCell>
                      {member.status === "active" ? (
                        <Button
                          variant="ghost"
                          size="xs"
                          disabled={busy}
                          onClick={() => setRemoveCode(member.code)}
                        >
                          移出
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
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
        open={removeCode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRemoveCode(null)
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>移出 {removeCode}？</AlertDialogTitle>
            <AlertDialogDescription>
              从当前池拿掉这只票，不删日线。以后还可以再加回来。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy || !removeCode}
              onClick={(event) => {
                event.preventDefault()
                if (removeCode) {
                  void onRemove(removeCode)
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

function Stat({
  label,
  value,
  loading,
}: {
  label: string
  value: number | undefined
  loading: boolean
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle>
          {loading && value === undefined ? "—" : (value ?? "—")}
        </CardTitle>
      </CardHeader>
    </Card>
  )
}
