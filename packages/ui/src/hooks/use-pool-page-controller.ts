import { useEffect, useMemo, useState, type FormEvent } from "react"

import { useJobs } from "@/components/job-provider"
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
import { withQueuedHint } from "@/lib/jobs"
import {
  activeMemberCodes,
  moveMemberDown,
  moveMemberToFirst,
  moveMemberUp,
} from "@/lib/member-order"
import { filterMembersByQuery } from "@/lib/member-query"
import { filterMembersByQuotePlan, type QuoteFilter } from "@/lib/quote-filter"
import { notify } from "@/lib/notify"
import { tickerFromCode } from "@/lib/ticker"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"

export function usePoolPageController() {
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
  const quotedMembers = useMemo(
    () => filterMembersByQuotePlan(members, quoteFilter),
    [members, quoteFilter]
  )
  const visibleMembers = useMemo(
    () => filterMembersByQuery(quotedMembers, memberQuery),
    [quotedMembers, memberQuery]
  )
  const selectedCode = useMemo(() => {
    if (!members?.length) return null
    const pickedInPool = Boolean(
      pickedCode && members.some((member) => member.code === pickedCode)
    )
    if (quotedMembers?.length)
      return pickedCode &&
        quotedMembers.some((member) => member.code === pickedCode)
        ? pickedCode
        : quotedMembers[0].code
    return pickedInPool ? pickedCode : members[0].code
  }, [members, pickedCode, quotedMembers])
  const visibleActiveCodes = useMemo(
    () =>
      (visibleMembers ?? [])
        .filter((member) => member.status === "active")
        .map((member) => member.code),
    [visibleMembers]
  )
  const fullActiveCodes = useMemo(() => activeMemberCodes(members), [members])
  const allVisibleChecked =
    visibleActiveCodes.length > 0 &&
    visibleActiveCodes.every((code) => checkedCodes.has(code))
  const someVisibleChecked =
    visibleActiveCodes.some((code) => checkedCodes.has(code)) &&
    !allVisibleChecked
  const showDetailPane =
    (loading && members === null) || Boolean(members?.length)

  async function loadAll(preferred?: string) {
    const [listing, settings] = await Promise.all([
      queryPools(),
      querySettings(),
    ])
    const nextId =
      listing.pools.find(
        (pool) => pool.id === (preferred ?? poolId ?? settings.pool)
      )?.id ??
      listing.pools[0]?.id ??
      null
    setPools(listing.pools)
    setPoolId(nextId)
    if (nextId) patchUiPrefs({ poolId: nextId })
    if (!nextId) {
      setStatus(null)
      setMembers([])
      setCheckedCodes(new Set())
      setEditing(false)
      return
    }
    const [nextStatus, listingMembers] = await Promise.all([
      queryStatus(nextId),
      queryPoolList(nextId),
    ])
    setStatus(nextStatus)
    setMembers(listingMembers.members)
    const codes = new Set(listingMembers.members.map((member) => member.code))
    setCheckedCodes(
      (prev) => new Set([...prev].filter((code) => codes.has(code)))
    )
  }
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await loadAll()
      } catch (err) {
        if (!cancelled)
          notify.error("股票池操作失败", {
            description: err instanceof Error ? err.message : "加载失败",
          })
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    } /* initial load only */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  async function run(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
    } catch (err) {
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
    if (!id) return
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
    if (!poolId) return
    const current = poolId
    await run(async () => {
      const job = await submitQuotesSync(current)
      trackJob(job, {
        onSuccess: async () => {
          notify.success("已同步当前池行情")
          await loadAll(current)
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
    if (!poolId) return
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
    if (!poolId) return
    await run(async () => {
      if (addMode === "codes") {
        await addPoolCodes(poolId, addCodes)
        notify.success("已按代码加入成分")
        await loadAll(poolId)
      } else {
        const current = poolId
        const job = await addPoolIndex(current, addIndex, replaceIndex)
        trackJob(job, {
          onSuccess: async () => {
            notify.success(
              replaceIndex
                ? `已用 ${addIndex} 覆盖当前池`
                : `已并入 ${addIndex}`
            )
            await loadAll(current)
          },
          onFailure: (done) =>
            notify.error("股票池操作失败", {
              description: done.error || "按指数添加失败",
            }),
        })
        notify.success(withQueuedHint(`已提交 ${addIndex} 成分任务`, jobs, job))
      }
      setAddOpen(false)
      setAddCodes("")
      setReplaceIndex(false)
    })
  }
  async function onRemove(codes: string[]) {
    if (!poolId || !codes.length) return
    await run(async () => {
      await removePoolCodes(poolId, codes)
      setRemoveCodes(null)
      setCheckedCodes((prev) => {
        const next = new Set(prev)
        codes.forEach((code) => next.delete(code))
        return next
      })
      notify.success(
        `已移出 ${codes.length === 1 ? tickerFromCode(codes[0]) : `${codes.length} 只`}`
      )
      await loadAll(poolId)
    })
  }
  async function onReorder(next: string[] | null) {
    if (!poolId || !next) return
    const current = activeMemberCodes(members)
    if (
      current.length === next.length &&
      current.every((code, index) => code === next[index])
    )
      return
    await run(async () => {
      await reorderPoolMembers(poolId, next)
      await loadAll(poolId)
    })
  }
  function toggleOne(code: string, checked: boolean) {
    setCheckedCodes((prev) => {
      const next = new Set(prev)
      checked ? next.add(code) : next.delete(code)
      return next
    })
  }
  function toggleAll(checked: boolean) {
    setCheckedCodes((prev) => {
      const next = new Set(prev)
      visibleActiveCodes.forEach((code) =>
        checked ? next.add(code) : next.delete(code)
      )
      return next
    })
  }
  async function onSelectPool(next: string | null) {
    if (!next || next === poolId) return
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
  function selectMember(code: string) {
    setPickedCode(code)
    patchUiPrefs({ pickedCode: code })
  }
  function setEdit(next: boolean) {
    setEditing(next)
    if (!next) setCheckedCodes(new Set())
  }
  function setFilter(filter: QuoteFilter) {
    setQuoteFilter(filter)
    patchUiPrefs({ quoteFilter: filter })
  }

  return {
    poolItems,
    poolId,
    pools,
    status,
    members,
    loading,
    busy,
    createOpen,
    createId,
    createName,
    deleteOpen,
    addOpen,
    addMode,
    addCodes,
    addIndex,
    replaceIndex,
    removeCodes,
    editing,
    checkedCodes,
    quoteFilter,
    memberQuery,
    selectedCode,
    visibleActiveCodes,
    allVisibleChecked,
    someVisibleChecked,
    showDetailPane,
    setCreateOpen,
    setCreateId,
    setCreateName,
    setDeleteOpen,
    setAddOpen,
    setAddMode,
    setAddCodes,
    setAddIndex,
    setReplaceIndex,
    setRemoveCodes,
    setMemberQuery,
    setLoading,
    setFilter,
    setEdit,
    selectMember,
    toggleOne,
    toggleAll,
    onSelectPool,
    onCreate,
    onSyncAll,
    onDelete,
    onAdd,
    onRemove,
    onMoveUp: (code: string) =>
      onReorder(moveMemberUp(fullActiveCodes, visibleActiveCodes, code)),
    onMoveDown: (code: string) =>
      onReorder(moveMemberDown(fullActiveCodes, visibleActiveCodes, code)),
    onMoveToFirst: (code: string) =>
      onReorder(moveMemberToFirst(fullActiveCodes, visibleActiveCodes, code)),
    onRefresh: () => {
      setLoading(true)
      return run(async () => loadAll(poolId ?? undefined))
    },
  }
}
