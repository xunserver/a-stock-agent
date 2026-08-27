import { useEffect, useState, type FormEvent } from "react"
import {
  CircleAlertIcon,
  LandmarkIcon,
  PlusIcon,
  RefreshCwIcon,
} from "lucide-react"

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
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  addStockCodes,
  addStockIndex,
  queryStocks,
  removeStockCodes,
  type StockRow,
  type StocksList,
} from "@/lib/api"
import { INDEX_OPTIONS } from "@/lib/indexes"

function poolLabel(stock: StockRow) {
  if (stock.pools.length === 0) {
    return "未入池，可以从系统移除"
  }
  const names = stock.pools.map((pool) => pool.name || pool.id).join("、")
  return `在 ${names} 中，无法从系统移除`
}

export function StocksPage() {
  const [listing, setListing] = useState<StocksList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [addOpen, setAddOpen] = useState(false)
  const [addMode, setAddMode] = useState<"codes" | "index">("codes")
  const [addCodes, setAddCodes] = useState("")
  const [addIndex, setAddIndex] = useState("hs300")
  const [removeCode, setRemoveCode] = useState<string | null>(null)

  const stocks = listing?.stocks ?? null
  const unpooled = listing ? listing.count - listing.in_pool : undefined

  async function loadAll() {
    setError(null)
    setListing(await queryStocks())
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

  async function onAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await run(async () => {
      if (addMode === "codes") {
        await addStockCodes(addCodes)
        setNotice("已按代码加入系统")
      } else {
        await addStockIndex(addIndex)
        setNotice(`已按 ${addIndex} 加入系统`)
      }
      setAddOpen(false)
      setAddCodes("")
      await loadAll()
    })
  }

  async function onRemove(code: string) {
    await run(async () => {
      await removeStockCodes([code])
      setRemoveCode(null)
      setNotice(`已从系统移除 ${code}`)
      await loadAll()
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>股票操作失败</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}
      {notice && !error ? (
        <Alert>
          <AlertTitle>已更新</AlertTitle>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="系统内" value={listing?.count} loading={loading} />
        <Stat label="在池中" value={listing?.in_pool} loading={loading} />
        <Stat label="未入池" value={unpooled} loading={loading} />
        <Stat label="已有资料" value={listing?.profile_filled} loading={loading} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>股票</CardTitle>
          <CardDescription>
            先决定系统里有哪些票。加入股票池之后，就不能从这里移除。
          </CardDescription>
          <CardAction>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => {
                  setAddMode("codes")
                  setAddOpen(true)
                }}
              >
                <PlusIcon data-icon="inline-start" />
                加入股票
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => {
                  setLoading(true)
                  void run(async () => {
                    await loadAll()
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
          {loading && stocks === null ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : stocks && stocks.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>行业</TableHead>
                  <TableHead>最新 K</TableHead>
                  <TableHead>所在池</TableHead>
                  <TableHead className="w-20">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stocks.map((stock) => {
                  const blocked = stock.pools.length > 0
                  return (
                    <TableRow key={stock.code}>
                      <TableCell className="font-mono">{stock.code}</TableCell>
                      <TableCell>{stock.name || "—"}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {stock.industry || "—"}
                      </TableCell>
                      <TableCell className="font-mono text-muted-foreground">
                        {stock.last_bar || "—"}
                      </TableCell>
                      <TableCell>
                        {blocked ? (
                          <div className="flex flex-wrap gap-1">
                            {stock.pools.map((pool) => (
                              <Badge key={pool.id} variant="secondary">
                                {pool.name || pool.id}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">未入池</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {blocked ? (
                          <Tooltip>
                            <TooltipTrigger
                              render={<span className="inline-flex" />}
                            >
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
                            onClick={() => setRemoveCode(stock.code)}
                          >
                            移除
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          ) : (
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
                  <Button
                    size="sm"
                    disabled={busy}
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
                    disabled={busy}
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

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <form className="flex flex-col gap-4" onSubmit={(event) => void onAdd(event)}>
            <DialogHeader>
              <DialogTitle>加入系统</DialogTitle>
              <DialogDescription>
                这里决定系统里有哪些股票的数据。加入股票池要到「股票池」页。指数拉取可能要几秒。
              </DialogDescription>
            </DialogHeader>
            <FieldGroup>
              <Field>
                <FieldTitle id="stock-add-mode-label">方式</FieldTitle>
                <ToggleGroup
                  aria-labelledby="stock-add-mode-label"
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
                  <FieldLabel htmlFor="stock-add-codes">股票代码</FieldLabel>
                  <Textarea
                    id="stock-add-codes"
                    required
                    value={addCodes}
                    placeholder="000001, 600519"
                    onChange={(event) => setAddCodes(event.target.value)}
                  />
                  <FieldDescription>逗号或换行分隔，6 位代码。</FieldDescription>
                </Field>
              ) : (
                <Field>
                  <FieldTitle id="stock-add-index-label">指数</FieldTitle>
                  <ToggleGroup
                    aria-labelledby="stock-add-index-label"
                    value={[addIndex]}
                    onValueChange={(next) => {
                      if (next[0]) {
                        setAddIndex(next[0])
                      }
                    }}
                    variant="outline"
                    spacing={0}
                  >
                    {INDEX_OPTIONS.map((option) => (
                      <ToggleGroupItem key={option.value} value={option.value}>
                        {option.label}
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </Field>
              )}
            </FieldGroup>
            <DialogFooter>
              <Button type="submit" disabled={busy}>
                {busy ? <Spinner data-icon="inline-start" /> : null}
                {addMode === "index" ? "拉取并加入" : "加入"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

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
            <AlertDialogTitle>从系统移除 {removeCode}？</AlertDialogTitle>
            <AlertDialogDescription>
              只从股票目录拿掉，不删日线。若还在股票池里，这里会拒绝。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={busy || !removeCode}
              onClick={(event) => {
                event.preventDefault()
                if (removeCode) {
                  void onRemove(removeCode)
                }
              }}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              移除
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
        <CardTitle>{loading && value === undefined ? "—" : (value ?? "—")}</CardTitle>
      </CardHeader>
    </Card>
  )
}
