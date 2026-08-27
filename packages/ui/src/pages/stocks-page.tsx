import { useEffect, useState, type FormEvent } from "react"
import {
  CircleAlertIcon,
  LandmarkIcon,
  PlusIcon,
  RefreshCwIcon,
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
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { TickerLink } from "@/components/ticker-link"
import {
  addStockCodes,
  addStockIndex,
  queryStocks,
  removeStockCodes,
  submitStockSync,
  type StockRow,
  type StocksList,
} from "@/lib/api"
import { INDEX_OPTIONS } from "@/lib/indexes"
import { withQueuedHint } from "@/lib/jobs"
import { tickerFromCode } from "@/lib/ticker"

function stockId(stock: Pick<StockRow, "code" | "ticker">): string {
  return stock.ticker || tickerFromCode(stock.code)
}

function poolLabel(stock: StockRow) {
  if (stock.pools.length === 0) {
    return "未入池，可以从系统移除"
  }
  const names = stock.pools.map((pool) => pool.name || pool.id).join("、")
  return `在 ${names} 中，无法从系统移除`
}

export function StocksPage() {
  const { trackJob, jobs } = useJobs()
  const [listing, setListing] = useState<StocksList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())

  const [addOpen, setAddOpen] = useState(false)
  const [addMode, setAddMode] = useState<"codes" | "index">("codes")
  const [addCodes, setAddCodes] = useState("")
  const [addIndex, setAddIndex] = useState("hs300")
  const [removeCode, setRemoveCode] = useState<string | null>(null)

  const stocks = listing?.stocks ?? null
  const selectedCount = selected.size
  const allSelected = Boolean(
    stocks && stocks.length > 0 && selectedCount === stocks.length
  )
  const someSelected = selectedCount > 0 && !allSelected

  async function loadAll() {
    setError(null)
    const next = await queryStocks()
    setListing(next)
    const codes = new Set(next.stocks.map((item) => item.code))
    setSelected((prev) => new Set([...prev].filter((code) => codes.has(code))))
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
        await loadAll()
      } else {
        const index = addIndex
        const job = await addStockIndex(index)
        trackJob(job, {
          onSuccess: async () => {
            setNotice(`已按 ${index} 加入系统`)
            await loadAll()
          },
          onFailure: (done) => setError(done.error || "按指数加入失败"),
        })
        setNotice(withQueuedHint(`已提交 ${index} 加入任务`, jobs, job))
      }
      setAddOpen(false)
      setAddCodes("")
    })
  }

  async function onRemove(code: string) {
    await run(async () => {
      await removeStockCodes([code])
      setRemoveCode(null)
      setNotice(`已从系统移除 ${tickerFromCode(code)}`)
      await loadAll()
    })
  }

  async function onSync(codes: string[]) {
    if (codes.length === 0) {
      return
    }
    await run(async () => {
      const label =
        codes.length === 1 ? tickerFromCode(codes[0]) : `${codes.length} 只`
      const job = await submitStockSync(codes)
      trackJob(job, {
        onSuccess: async () => {
          setNotice(`已同步 ${label} 的资料与行情`)
          await loadAll()
        },
        onFailure: (done) => setError(done.error || "同步失败"),
      })
      setNotice(withQueuedHint(`已提交 ${label} 的同步任务`, jobs, job))
    })
  }

  function toggleOne(code: string, checked: boolean) {
    setSelected((prev) => {
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
    if (!stocks || !checked) {
      setSelected(new Set())
      return
    }
    setSelected(new Set(stocks.map((item) => item.code)))
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

      <Card>
        <CardHeader>
          <CardTitle>股票</CardTitle>
          <CardAction>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={busy || selectedCount === 0}
                onClick={() => void onSync([...selected])}
              >
                {busy ? <Spinner data-icon="inline-start" /> : null}
                同步所选{selectedCount > 0 ? ` ${selectedCount}` : ""}
              </Button>
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
                  <TableHead className="w-8">
                    <Checkbox
                      aria-label="全选"
                      checked={allSelected}
                      indeterminate={someSelected}
                      disabled={busy}
                      onCheckedChange={(checked) => toggleAll(checked)}
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
                            toggleOne(stock.code, next === true)
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
                            onClick={() => void onSync([stock.code])}
                          >
                            同步
                          </Button>
                          {blocked ? (
                            <Tooltip>
                              <TooltipTrigger
                                render={<span className="inline-flex" />}
                              >
                                <Button variant="ghost" size="xs" disabled>
                                  移除
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {poolLabel(stock)}
                              </TooltipContent>
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
                        </div>
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
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => void onAdd(event)}
          >
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
                    placeholder="000001.SZ, 600519.SS"
                    onChange={(event) => setAddCodes(event.target.value)}
                  />
                  <FieldDescription>
                    逗号或换行分隔。6 位代码或带交易所后缀，例如 000001.SZ。
                  </FieldDescription>
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
                    className="w-full max-w-full flex-wrap"
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
            <AlertDialogTitle>
              从系统移除 {removeCode ? tickerFromCode(removeCode) : ""}？
            </AlertDialogTitle>
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
