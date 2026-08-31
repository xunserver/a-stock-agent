import { useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router"

import { useJobs } from "@/components/job-provider"
import {
  pickOpenAnalyzeJob,
  reportSectionText,
  type ReportSectionId,
} from "@/components/analyze/analyze-model"
import {
  getAnalyzeReport,
  listAnalyzeReports,
  queryPoolList,
  queryPools,
  querySettings,
  submitAnalyzeRun,
  type AnalystKind,
  type AnalyzeReportDetail,
  type AnalyzeReportSummary,
  type Job,
  type PoolMember,
  type PoolSummary,
  type Settings,
} from "@/lib/api"
import { isOpenJob, pickJobString } from "@/lib/jobs"
import { notify } from "@/lib/notify"

export function useAnalyzePageController() {
  const { trackJob, jobs } = useJobs()
  const [searchParams, setSearchParams] = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [settings, setSettings] = useState<Settings | null>(null)
  const [pools, setPools] = useState<PoolSummary[]>([])
  const [poolId, setPoolId] = useState<string>("")
  const [members, setMembers] = useState<PoolMember[]>([])
  const [code, setCode] = useState("")
  const [date, setDate] = useState("")
  const [analysts, setAnalysts] = useState<AnalystKind[]>([
    "market",
    "news",
    "fundamentals",
  ])

  const [job, setJob] = useState<Job | null>(null)
  const [logs, setLogs] = useState<string[]>([])

  const [reports, setReports] = useState<AnalyzeReportSummary[]>([])
  const [filterByCode, setFilterByCode] = useState(false)
  const [opened, setOpened] = useState<AnalyzeReportDetail | null>(null)
  const [section, setSection] = useState<ReportSectionId>("summary")
  const [reportLoading, setReportLoading] = useState(false)
  const [reportsLoading, setReportsLoading] = useState(false)

  const logEndRef = useRef<HTMLDivElement>(null)
  const reportCardRef = useRef<HTMLDivElement>(null)

  function reportError(message: string) {
    notify.error("分析页出错", { description: message })
  }
  const completedJobRef = useRef<string | null>(null)
  const urlApplied = useRef(false)
  const poolIdRef = useRef(poolId)
  const filterByCodeRef = useRef(filterByCode)

  poolIdRef.current = poolId
  filterByCodeRef.current = filterByCode

  const poolItems = useMemo(
    () =>
      pools.map((pool) => ({
        label: `${pool.name} · ${pool.id}`,
        value: pool.id,
      })),
    [pools]
  )
  const memberItems = useMemo(
    () =>
      members
        .filter((member) => member.status === "active")
        .map((member) => ({
          label: `${member.code} ${member.name || ""}`.trim(),
          value: member.code,
        })),
    [members]
  )
  const selectedMember = members.find((member) => member.code === code) ?? null
  const provider = settings?.analyze.llm_provider
  const needsKey =
    settings !== null &&
    provider !== "ollama" &&
    provider !== "openai_compatible" &&
    !settings.analyze.api_key_set
  const needsBackend =
    settings !== null &&
    provider === "openai_compatible" &&
    !settings.analyze.backend_url.trim()
  const needsModels =
    settings !== null &&
    !settings.analyze.deep_think_llm.trim() &&
    !settings.analyze.quick_think_llm.trim()
  const canSubmit =
    Boolean(poolId && code && date && analysts.length > 0) &&
    !needsKey &&
    !needsBackend &&
    !needsModels &&
    !submitting
  const hasRunning = jobs.some(
    (item) => item.type === "analyze.run" && isOpenJob(item.status)
  )

  function attachJob(next: Job) {
    setJob(next)
    setLogs(next.log ?? [])
  }

  async function loadMembers(nextPool: string, preferredCode?: string | null) {
    const listing = await queryPoolList(nextPool)
    const active = listing.members.filter(
      (member) => member.status === "active"
    )
    setMembers(listing.members)
    const nextCode =
      (preferredCode && active.some((member) => member.code === preferredCode)
        ? preferredCode
        : null) ??
      active[0]?.code ??
      ""
    setCode(nextCode)
    const member = active.find((item) => item.code === nextCode)
    if (member?.last_bar && !searchParams.get("date")) {
      setDate(member.last_bar)
    }
    return nextCode
  }

  async function loadReports(nextPool: string, nextCode?: string) {
    setReportsLoading(true)
    try {
      const listing = await listAnalyzeReports({
        pool: nextPool,
        ...(nextCode ? { code: nextCode } : {}),
      })
      setReports(listing.reports)
    } finally {
      setReportsLoading(false)
    }
  }

  async function loadReport(
    nextCode: string,
    nextDate: string,
    runId?: string
  ) {
    setReportLoading(true)
    try {
      const detail = await getAnalyzeReport({
        code: nextCode,
        date: nextDate,
        run_id: runId,
      })
      setOpened(detail)
      setSection("summary")
      const params = new URLSearchParams()
      params.set("code", detail.code || nextCode)
      params.set("date", detail.date || nextDate)
      const resolvedRun = detail.run_id || runId
      if (resolvedRun) {
        params.set("run", resolvedRun)
      }
      setSearchParams(params, { replace: true })
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "读取报告失败")
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [nextSettings, listing] = await Promise.all([
          querySettings(),
          queryPools(),
        ])
        if (cancelled) {
          return
        }
        setSettings(nextSettings)
        setPools(listing.pools)
        setAnalysts(
          nextSettings.analyze.analysts.length > 0
            ? nextSettings.analyze.analysts
            : ["market", "news", "fundamentals"]
        )
        const urlCode = searchParams.get("code")
        const urlDate = searchParams.get("date")
        const urlRun = searchParams.get("run")
        const urlPool = searchParams.get("pool")
        if (urlCode) {
          setFilterByCode(true)
        }
        const preferredPool =
          listing.pools.find((pool) => pool.id === urlPool)?.id ??
          listing.pools.find((pool) => pool.id === nextSettings.pool)?.id ??
          listing.pools[0]?.id ??
          ""
        setPoolId(preferredPool)
        if (urlDate) {
          setDate(urlDate)
        }
        if (preferredPool) {
          await loadMembers(preferredPool, urlCode)
          await loadReports(preferredPool, urlCode ?? undefined)
        }
        if (urlCode && urlDate && !urlApplied.current) {
          urlApplied.current = true
          await loadReport(urlCode, urlDate, urlRun ?? undefined)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          reportError(err instanceof Error ? err.message : "加载失败")
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
    // First paint only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const live = job
      ? jobs.find((item) => item.id === job.id)
      : pickOpenAnalyzeJob(jobs)
    if (!live) return
    setJob(live)
    setLogs(live.log ?? [])
    if (live.status !== "succeeded" || completedJobRef.current === live.id)
      return
    completedJobRef.current = live.id
    const reportCode = pickJobString(live, "code")
    const reportDate = pickJobString(live, "date")
    const runId = pickJobString(live, "run_id")
    if (reportCode && reportDate) {
      void loadReport(reportCode, reportDate, runId ?? undefined)
      void loadReports(
        poolIdRef.current,
        filterByCodeRef.current ? reportCode : undefined
      )
    }
    // loadReport/loadReports are page use-cases with refs for current filters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, job?.id])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" })
  }, [logs])

  async function onSelectPool(next: string | null) {
    if (!next || next === poolId) {
      return
    }
    setPoolId(next)
    try {
      const nextCode = await loadMembers(next)
      await loadReports(next, filterByCode ? nextCode : undefined)
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "加载股票池失败")
    }
  }

  async function onSelectCode(next: string | null) {
    if (!next) {
      return
    }
    setCode(next)
    const member = members.find((item) => item.code === next)
    if (member?.last_bar) {
      setDate(member.last_bar)
    }
    if (filterByCode) {
      try {
        await loadReports(poolId, next)
      } catch (err: unknown) {
        reportError(err instanceof Error ? err.message : "加载报告失败")
      }
    }
  }

  async function onToggleFilter(checked: boolean) {
    setFilterByCode(checked)
    try {
      await loadReports(poolId, checked ? code : undefined)
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "加载报告失败")
    }
  }

  async function onSubmit() {
    if (!canSubmit) {
      return
    }
    setSubmitting(true)
    try {
      const next = await submitAnalyzeRun({
        pool: poolId,
        code,
        date,
        analysts,
      })
      attachJob(next)
      trackJob(next)
    } catch (err: unknown) {
      reportError(err instanceof Error ? err.message : "提交失败")
    } finally {
      setSubmitting(false)
    }
  }

  const decision =
    job && job.status === "succeeded" ? pickJobString(job, "decision") : null
  const openedText = opened ? reportSectionText(opened, section) : ""

  function onOpenJobReport(selectedJob: Job) {
    const reportCode = pickJobString(selectedJob, "code")
    const reportDate = pickJobString(selectedJob, "date")
    const runId = pickJobString(selectedJob, "run_id")
    if (reportCode && reportDate) {
      void loadReport(reportCode, reportDate, runId ?? undefined)
    }
    reportCardRef.current?.scrollIntoView({ block: "start" })
  }

  return {
    loading: loading && settings === null,
    poolItems,
    memberItems,
    poolId,
    code,
    date,
    analysts,
    selectedMember,
    needsKey,
    needsBackend,
    needsModels,
    hasRunning,
    canSubmit,
    submitting,
    job,
    jobs,
    logs,
    decision,
    logEndRef,
    reports,
    reportsLoading,
    filterByCode,
    reportLoading,
    opened,
    section,
    openedText,
    reportCardRef,
    setDate,
    setAnalysts,
    setSection,
    onSelectPool,
    onSelectCode,
    onToggleFilter,
    onSubmit,
    onOpenJobReport,
    loadReport,
  }
}
