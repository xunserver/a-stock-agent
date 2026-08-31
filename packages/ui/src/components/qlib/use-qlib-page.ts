import { useEffect, useMemo, useRef, useState } from "react"

import { useJobs } from "@/components/job-provider"
import {
  getQlibRun,
  listQlibRuns,
  queryPools,
  queryQlibOverview,
  saveQlibWorkflow,
  submitQlibDump,
  submitQlibRun,
  type PoolSummary,
  type QlibOverview,
  type QlibRun,
  type QlibWorkflow,
} from "@/lib/api"
import { isOpenJob } from "@/lib/jobs"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"

import { copyWorkflow, isQlibPoolJob, jobPool } from "./helpers"

export function useQlibPage() {
  const { jobs, trackJob } = useJobs()
  const [pools, setPools] = useState<PoolSummary[]>([])
  const [poolId, setPoolId] = useState(() => readUiPrefs().poolId ?? "")
  const [overview, setOverview] = useState<QlibOverview | null>(null)
  const [runs, setRuns] = useState<QlibRun[]>([])
  const [selectedRun, setSelectedRun] = useState<QlibRun | null>(null)
  const [workflow, setWorkflow] = useState<QlibWorkflow | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [preparing, setPreparing] = useState(false)
  const poolIdRef = useRef(poolId)
  const watchedJobRef = useRef<string | null>(null)
  poolIdRef.current = poolId
  const poolItems = useMemo(
    () =>
      pools.map((pool) => ({
        value: pool.id,
        label: `${pool.name} · ${pool.id}`,
      })),
    [pools]
  )
  const openPoolJob = useMemo(
    () =>
      jobs.find(
        (job) =>
          isQlibPoolJob(job) && jobPool(job) === poolId && isOpenJob(job.status)
      ) ?? null,
    [jobs, poolId]
  )
  const openRunJob = openPoolJob?.type === "qlib.run" ? openPoolJob : null
  const openDumpJob = openPoolJob?.type === "qlib.dump" ? openPoolJob : null
  async function loadPool(nextPool: string, preferredRun?: string) {
    const [nextOverview, nextRuns] = await Promise.all([
      queryQlibOverview(nextPool),
      listQlibRuns(nextPool),
    ])
    setOverview(nextOverview)
    setRuns(nextRuns)
    setWorkflow(copyWorkflow(nextOverview.workflow))
    const runId = preferredRun ?? nextOverview.latest_run?.run_id
    if (!runId) {
      setSelectedRun(null)
      return
    }
    const summary = nextRuns.find((run) => run.run_id === runId)
    setSelectedRun(
      runId === nextOverview.latest_run?.run_id && nextOverview.latest_run
        ? nextOverview.latest_run
        : summary
          ? await getQlibRun(summary.run_id)
          : null
    )
  }
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const listing = await queryPools()
        if (cancelled) return
        const nextPool =
          listing.pools.find((pool) => pool.id === poolId)?.id ??
          listing.pools[0]?.id ??
          ""
        setPools(listing.pools)
        setPoolId(nextPool)
        if (nextPool) {
          patchUiPrefs({ poolId: nextPool })
          await loadPool(nextPool)
        }
      } catch {
        /* Errors surface in the job panel or leave the page in its last state. */
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (openPoolJob) {
      watchedJobRef.current = openPoolJob.id
      return
    }
    if (!watchedJobRef.current || !poolId) return
    watchedJobRef.current = null
    void loadPool(poolId).catch(() => {
      /* Refresh failures stay visible in the job panel. */
    }) // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openPoolJob, poolId])
  async function onSelectPool(value: string | null) {
    if (!value || value === poolId) return
    setPoolId(value)
    patchUiPrefs({ poolId: value })
    setLoading(true)
    try {
      await loadPool(value)
    } catch {
      /* Keep the previous pool view when reload fails. */
    } finally {
      setLoading(false)
    }
  }
  async function onSelectRun(value: string) {
    if (value === selectedRun?.run_id) return
    try {
      setSelectedRun(await getQlibRun(value))
    } catch {
      /* Keep the previously selected run when history fetch fails. */
    }
  }
  function patchWorkflow(patch: Partial<QlibWorkflow>) {
    setWorkflow((current) => (current ? { ...current, ...patch } : current))
  }
  async function onPrepare() {
    if (!poolId || openPoolJob) return
    const submittedPool = poolId
    setPreparing(true)
    try {
      const job = await submitQlibDump(poolId)
      trackJob(job, {
        onSuccess: async () => {
          if (poolIdRef.current === submittedPool)
            await loadPool(submittedPool, selectedRun?.run_id)
        },
      })
    } catch {
      /* Submission errors are shown in the job panel. */
    } finally {
      setPreparing(false)
    }
  }
  async function onRun() {
    if (!poolId || !workflow || openPoolJob || !overview?.data.ready) return
    const submittedPool = poolId
    setSubmitting(true)
    try {
      await saveQlibWorkflow(poolId, workflow)
      const job = await submitQlibRun(poolId, workflow)
      trackJob(job, {
        onSuccess: async () => {
          if (poolIdRef.current === submittedPool) await loadPool(submittedPool)
        },
      })
    } catch {
      /* Submission errors are shown in the job panel. */
    } finally {
      setSubmitting(false)
    }
  }
  return {
    loading,
    poolId,
    poolItems,
    overview,
    runs,
    selectedRun,
    workflow,
    submitting,
    preparing,
    openPoolJob,
    openRunJob,
    openDumpJob,
    onSelectPool,
    onSelectRun,
    patchWorkflow,
    onPrepare,
    onRun,
  }
}
