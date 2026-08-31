import { useEffect, useState, type FormEvent } from "react"

import { useJobs } from "@/components/job-provider"
import { AddStockDialog } from "@/components/stocks/add-stock-dialog"
import { RemoveStockDialog } from "@/components/stocks/remove-stock-dialog"
import { StocksCard } from "@/components/stocks/stocks-card"
import {
  addStockCodes,
  addStockIndex,
  queryStocks,
  removeStockCodes,
  submitStockSync,
  type StocksList,
} from "@/lib/api"
import { withQueuedHint } from "@/lib/jobs"
import { notify } from "@/lib/notify"
import { tickerFromCode } from "@/lib/ticker"

export function StocksPage() {
  const { trackJob, jobs } = useJobs()
  const [listing, setListing] = useState<StocksList | null>(null)
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
        if (!cancelled)
          notify.error("股票操作失败", {
            description: err instanceof Error ? err.message : "加载失败",
          })
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
    } catch (err: unknown) {
      notify.error("股票操作失败", {
        description: err instanceof Error ? err.message : "操作失败",
      })
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
        notify.success("已按代码加入系统")
        await loadAll()
      } else {
        const index = addIndex
        const job = await addStockIndex(index)
        trackJob(job, {
          onSuccess: async () => {
            notify.success(`已按 ${index} 加入系统`)
            await loadAll()
          },
          onFailure: (done) =>
            notify.error("股票操作失败", {
              description: done.error || "按指数加入失败",
            }),
        })
        notify.success(withQueuedHint(`已提交 ${index} 加入任务`, jobs, job))
      }
      setAddOpen(false)
      setAddCodes("")
    })
  }

  async function onRemove(code: string) {
    await run(async () => {
      await removeStockCodes([code])
      setRemoveCode(null)
      notify.success(`已从系统移除 ${tickerFromCode(code)}`)
      await loadAll()
    })
  }

  async function onSync(codes: string[]) {
    if (codes.length === 0) return
    await run(async () => {
      const label =
        codes.length === 1 ? tickerFromCode(codes[0]) : `${codes.length} 只`
      const job = await submitStockSync(codes)
      trackJob(job, {
        onSuccess: async () => {
          notify.success(`已同步 ${label} 的资料与行情`)
          await loadAll()
        },
        onFailure: (done) =>
          notify.error("股票操作失败", {
            description: done.error || "同步失败",
          }),
      })
      notify.success(withQueuedHint(`已提交 ${label} 的同步任务`, jobs, job))
    })
  }

  function toggleOne(code: string, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(code)
      else next.delete(code)
      return next
    })
  }

  function toggleAll(checked: boolean) {
    setSelected(
      !stocks || !checked ? new Set() : new Set(stocks.map((item) => item.code))
    )
  }

  function openAdd(mode: "codes" | "index") {
    setAddMode(mode)
    setAddOpen(true)
  }

  return (
    <div className="flex flex-col gap-4">
      <StocksCard
        stocks={stocks}
        loading={loading}
        busy={busy}
        selected={selected}
        selectedCount={selectedCount}
        allSelected={allSelected}
        someSelected={someSelected}
        onSync={(codes) => void onSync(codes)}
        onToggleOne={toggleOne}
        onToggleAll={toggleAll}
        onRemove={setRemoveCode}
        onAdd={openAdd}
        onRefresh={() => {
          setLoading(true)
          void run(loadAll)
        }}
      />
      <AddStockDialog
        open={addOpen}
        busy={busy}
        mode={addMode}
        codes={addCodes}
        index={addIndex}
        onOpenChange={setAddOpen}
        onModeChange={setAddMode}
        onCodesChange={setAddCodes}
        onIndexChange={setAddIndex}
        onSubmit={(event) => void onAdd(event)}
      />
      <RemoveStockDialog
        code={removeCode}
        busy={busy}
        onOpenChange={(open) => {
          if (!open) setRemoveCode(null)
        }}
        onRemove={(code) => void onRemove(code)}
      />
    </div>
  )
}
