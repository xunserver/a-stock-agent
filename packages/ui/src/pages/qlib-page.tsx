import { useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router"
import {
  BrainIcon,
  DatabaseIcon,
  SparklesIcon,
} from "lucide-react"

import { useJobs } from "@/components/job-provider"
import { TickerLink } from "@/components/ticker-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Field,
  FieldGroup,
  FieldLabel,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  getQlibRun,
  listQlibRuns,
  queryPools,
  queryQlibOverview,
  saveQlibWorkflow,
  submitQlibDump,
  submitQlibRun,
  type Job,
  type PoolSummary,
  type QlibOverview,
  type QlibRun,
  type QlibWorkflow,
} from "@/lib/api"
import { formatJobDateTime, isOpenJob } from "@/lib/jobs"
import { changeTextClass } from "@/lib/change"
import { fmtPct } from "@/lib/financial-metrics"
import { patchUiPrefs, readUiPrefs } from "@/lib/ui-prefs"
import { cn } from "@/lib/utils"

const WORKFLOW_OPTIONS = [
  { value: "workflow_lightgbm_alpha158", label: "LightGBM + Alpha158" },
  { value: "workflow_lightgbm_focus5", label: "LightGBM + Focus5" },
]

const TOP_DISPLAY_OPTIONS = [5, 10, 20, 50] as const

function jobPool(job: Job): string {
  return typeof job.command.pool === "string" ? job.command.pool : ""
}

function formatScore(score: number): string {
  return Number.isFinite(score) ? score.toFixed(6) : "—"
}

function copyWorkflow(workflow: QlibWorkflow): QlibWorkflow {
  return {
    config: workflow.config,
    benchmark: workflow.benchmark,
    topk: workflow.topk,
    n_drop: workflow.n_drop,
    account: workflow.account,
    data_end: workflow.data_end ?? null,
    test_start: workflow.test_start ?? null,
    learning_rate: workflow.learning_rate ?? null,
  }
}

function isQlibPoolJob(job: Job): boolean {
  return job.type === "qlib.run" || job.type === "qlib.dump"
}

export function QlibPage() {
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
  const [displayTop, setDisplayTop] = useState<number>(TOP_DISPLAY_OPTIONS[1])
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
          isQlibPoolJob(job) &&
          jobPool(job) === poolId &&
          isOpenJob(job.status)
      ) ?? null,
    [jobs, poolId]
  )
  const openRunJob =
    openPoolJob?.type === "qlib.run" ? openPoolJob : null
  const openDumpJob =
    openPoolJob?.type === "qlib.dump" ? openPoolJob : null

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
        // Errors surface in the job panel or leave the page in its last state.
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // First paint only; later changes go through onSelectPool.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (openPoolJob) {
      watchedJobRef.current = openPoolJob.id
      return
    }
    if (!watchedJobRef.current || !poolId) return
    watchedJobRef.current = null
    void loadPool(poolId).catch(() => {
      // Refresh after a job finishes; failures stay visible in the job panel.
    })
    // loadPool intentionally follows the currently selected pool.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openPoolJob, poolId])

  async function onSelectPool(value: string | null) {
    if (!value || value === poolId) return
    setPoolId(value)
    patchUiPrefs({ poolId: value })
    setLoading(true)
    try {
      await loadPool(value)
    } catch {
      // Keep the previous pool view when reload fails.
    } finally {
      setLoading(false)
    }
  }

  async function onSelectRun(value: string | null) {
    if (!value || value === selectedRun?.run_id) return
    try {
      setSelectedRun(await getQlibRun(value))
    } catch {
      // Keep the previously selected run when history fetch fails.
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
          if (poolIdRef.current === submittedPool) {
            await loadPool(submittedPool, selectedRun?.run_id)
          }
        },
      })
    } catch {
      // Submission errors are shown in the job panel.
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
          if (poolIdRef.current === submittedPool) {
            await loadPool(submittedPool)
          }
        },
      })
    } catch {
      // Submission errors are shown in the job panel.
    } finally {
      setSubmitting(false)
    }
  }

  const candidates = selectedRun?.candidates ?? []
  const topOptions = useMemo(() => {
    const max = candidates.length
    if (max === 0) {
      return []
    }
    const values = new Set<number>()
    for (const value of TOP_DISPLAY_OPTIONS) {
      if (value <= max) {
        values.add(value)
      }
    }
    values.add(max)
    return [...values]
      .sort((left, right) => left - right)
      .map((value) => ({
        value: String(value),
        label: `Top ${value}`,
      }))
  }, [candidates.length])
  const visibleTop = topOptions.some((item) => Number(item.value) === displayTop)
    ? displayTop
    : Number(topOptions[topOptions.length - 1]?.value ?? displayTop)
  const visibleCandidates = useMemo(
    () => candidates.slice(0, visibleTop),
    [candidates, visibleTop]
  )
  const nextDayColumnLabel = selectedRun?.next_trade_date
    ? `次日涨跌 (${selectedRun.next_trade_date.slice(5)})`
    : "次日涨跌"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">量化选股</h1>
        <Select
          items={poolItems}
          value={poolId || null}
          onValueChange={(value) =>
            void onSelectPool(typeof value === "string" ? value : null)
          }
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
      </div>

      {loading || !workflow || !overview ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Workflow</CardTitle>
              <CardAction>
                <Badge variant={overview.data.ready ? "default" : "outline"}>
                  {overview.data.ready ? "数据就绪" : "请先准备数据"}
                </Badge>
              </CardAction>
            </CardHeader>
            <CardContent>
              <FieldGroup className="grid md:grid-cols-2">
                <Field>
                  <FieldLabel>配置模板</FieldLabel>
                  <Select
                    items={WORKFLOW_OPTIONS}
                    value={workflow.config}
                    onValueChange={(value) => {
                      if (typeof value === "string") {
                        patchWorkflow({ config: value })
                      }
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {WORKFLOW_OPTIONS.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-benchmark">回测基准</FieldLabel>
                  <Input
                    id="qlib-benchmark"
                    value={workflow.benchmark}
                    onChange={(event) =>
                      patchWorkflow({ benchmark: event.target.value })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-topk">候选只数</FieldLabel>
                  <Input
                    id="qlib-topk"
                    type="number"
                    min={1}
                    max={overview.pool.active}
                    value={workflow.topk}
                    onChange={(event) =>
                      patchWorkflow({ topk: Number(event.target.value) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-drop">每期换出</FieldLabel>
                  <Input
                    id="qlib-drop"
                    type="number"
                    min={0}
                    max={100}
                    value={workflow.n_drop}
                    onChange={(event) =>
                      patchWorkflow({ n_drop: Number(event.target.value) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-account">回测本金</FieldLabel>
                  <Input
                    id="qlib-account"
                    type="number"
                    min={1}
                    value={workflow.account}
                    onChange={(event) =>
                      patchWorkflow({ account: Number(event.target.value) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-data-end">数据截止日</FieldLabel>
                  <Input
                    id="qlib-data-end"
                    placeholder="YYYY-MM-DD，留空用最新"
                    value={workflow.data_end ?? ""}
                    onChange={(event) =>
                      patchWorkflow({
                        data_end: event.target.value.trim() || null,
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-test-start">测试区间起始</FieldLabel>
                  <Input
                    id="qlib-test-start"
                    placeholder="YYYY-MM-DD，留空用模板默认"
                    value={workflow.test_start ?? ""}
                    onChange={(event) =>
                      patchWorkflow({
                        test_start: event.target.value.trim() || null,
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="qlib-lr">学习率</FieldLabel>
                  <Input
                    id="qlib-lr"
                    type="number"
                    min={0.0001}
                    max={1}
                    step={0.01}
                    placeholder="留空用模板默认"
                    value={workflow.learning_rate ?? ""}
                    onChange={(event) => {
                      const raw = event.target.value.trim()
                      patchWorkflow({
                        learning_rate: raw ? Number(raw) : null,
                      })
                    }}
                  />
                </Field>
              </FieldGroup>
            </CardContent>
            <CardFooter className="flex flex-wrap gap-2">
              <Button
                disabled={
                  submitting ||
                  Boolean(openPoolJob) ||
                  !overview.data.ready
                }
                onClick={() => void onRun()}
              >
                {submitting || openRunJob ? (
                  <Spinner data-icon="inline-start" />
                ) : (
                  <SparklesIcon data-icon="inline-start" />
                )}
                {openRunJob
                  ? "选股运行中"
                  : overview.data.ready
                    ? "运行选股"
                    : "请先准备数据"}
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>池数据</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">选股范围</span>
                <span>池成员 {overview.pool.active} 只</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">已准备标的</span>
                <span>{overview.data.symbol_count} 只</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">行情区间</span>
                <span>
                  {overview.data.calendar_first && overview.data.calendar_last
                    ? `${overview.data.calendar_first} ~ ${overview.data.calendar_last}`
                    : "尚未准备"}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">最近准备</span>
                <span>
                  {overview.data.prepared_at
                    ? formatJobDateTime(overview.data.prepared_at)
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">最近运行</span>
                <span>{overview.latest_run?.as_of ?? "尚未运行"}</span>
              </div>
            </CardContent>
            <CardFooter>
              <Button
                variant="outline"
                className="w-full"
                disabled={preparing || Boolean(openPoolJob)}
                onClick={() => void onPrepare()}
              >
                {preparing || openDumpJob ? (
                  <Spinner data-icon="inline-start" />
                ) : (
                  <DatabaseIcon data-icon="inline-start" />
                )}
                {openDumpJob ? "准备数据中" : "准备数据"}
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}

      {runs.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>运行记录</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 p-2">
            {runs.map((run) => {
              const selected = run.run_id === selectedRun?.run_id
              return (
                <button
                  key={run.run_id}
                  type="button"
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
                    selected
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-muted/60"
                  )}
                  onClick={() => void onSelectRun(run.run_id)}
                >
                  <span className="font-medium">{run.as_of}</span>
                  <span className="text-muted-foreground text-xs">
                    {formatJobDateTime(run.created_at)}
                    {run.candidate_count != null
                      ? ` · ${run.candidate_count} 只`
                      : ""}
                  </span>
                </button>
              )
            })}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>
            {selectedRun
              ? `${selectedRun.as_of} 候选结果`
              : "候选结果"}
          </CardTitle>
          {candidates.length > 0 ? (
            <CardAction>
              <Select
                items={topOptions}
                value={String(visibleTop)}
                onValueChange={(value) => {
                  if (typeof value === "string") {
                    setDisplayTop(Number(value))
                  }
                }}
              >
                <SelectTrigger className="min-w-28">
                  <SelectValue placeholder="Top" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {topOptions.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          {candidates.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <SparklesIcon />
                </EmptyMedia>
                <EmptyTitle>还没有候选结果</EmptyTitle>
              </EmptyHeader>
              <EmptyContent>
                <Button
                  disabled={
                    !workflow ||
                    submitting ||
                    Boolean(openPoolJob) ||
                    !overview?.data.ready
                  }
                  onClick={() => void onRun()}
                >
                  运行选股
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">排名</TableHead>
                  <TableHead>股票</TableHead>
                  <TableHead>Qlib Symbol</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead className="text-right">{nextDayColumnLabel}</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleCandidates.map((candidate) => (
                  <TableRow key={candidate.code}>
                    <TableCell>{candidate.rank}</TableCell>
                    <TableCell>
                      <TickerLink code={candidate.code}>
                        {candidate.name
                          ? `${candidate.code} ${candidate.name}`
                          : candidate.code}
                      </TickerLink>
                    </TableCell>
                    <TableCell>{candidate.symbol}</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatScore(candidate.score)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right font-mono tabular-nums",
                        changeTextClass(candidate.next_day_pct_chg)
                      )}
                    >
                      {fmtPct(candidate.next_day_pct_chg)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        nativeButton={false}
                        render={
                          <Link
                            to={`/analyze?pool=${encodeURIComponent(poolId)}&code=${candidate.code}`}
                          />
                        }
                      >
                        <BrainIcon data-icon="inline-start" />
                        分析
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
