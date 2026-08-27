import { useEffect, useMemo, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router"
import { CircleAlertIcon, FileTextIcon, InfoIcon } from "lucide-react"

import { useJobs } from "@/components/job-provider"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
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
import { TickerLink } from "@/components/ticker-link"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  getAnalyzeReport,
  getJob,
  listAnalyzeReports,
  listJobs,
  queryPoolList,
  queryPools,
  querySettings,
  submitAnalyzeRun,
  watchJob,
  type AnalystKind,
  type AnalyzeReportDetail,
  type AnalyzeReportSummary,
  type Job,
  type PoolMember,
  type PoolSummary,
  type Settings,
} from "@/lib/api"
import {
  formatJobDateTime,
  isOpenJob,
  jobQueuedHint,
  jobStatusLabel,
  jobStatusVariant,
  pickJobString,
} from "@/lib/jobs"

const ANALYST_OPTIONS: { id: AnalystKind; label: string }[] = [
  { id: "market", label: "技术" },
  { id: "news", label: "新闻" },
  { id: "fundamentals", label: "基本面" },
  { id: "social", label: "情绪" },
]

const REPORT_SECTIONS = [
  { id: "summary", label: "摘要" },
  { id: "market", label: "技术" },
  { id: "news", label: "新闻" },
  { id: "fundamentals", label: "基本面" },
  { id: "research", label: "研究" },
  { id: "trading", label: "交易" },
  { id: "risk", label: "风险" },
  { id: "portfolio", label: "组合" },
  { id: "full", label: "全文" },
] as const

type ReportSectionId = (typeof REPORT_SECTIONS)[number]["id"]

function isAnalyst(value: string): value is AnalystKind {
  return (
    value === "market" ||
    value === "social" ||
    value === "news" ||
    value === "fundamentals"
  )
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function pickOpenAnalyzeJob(jobs: Job[]): Job | null {
  const open = jobs.filter(
    (job) => job.type === "analyze.run" && isOpenJob(job.status)
  )
  return (
    open.find((job) => job.status === "running") ??
    [...open].sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ??
    null
  )
}

function collectMarkdown(report: AnalyzeReportDetail, keys: string[]): string {
  const root = asRecord(report)
  const meta = asRecord(report.meta)
  const sections = asRecord(report.sections)
  const bags = [sections, root, meta]
  for (const nested of [
    "analysts",
    "research",
    "trading",
    "risk",
    "portfolio",
    "1_analysts",
    "2_research",
    "3_trading",
    "4_risk",
    "5_portfolio",
  ]) {
    bags.push(
      asRecord(root[nested]),
      asRecord(sections[nested]),
      asRecord(meta[nested])
    )
  }
  const parts: string[] = []
  for (const key of keys) {
    let found = ""
    for (const alias of [key, `${key}.md`]) {
      for (const bag of bags) {
        const value = bag[alias]
        if (typeof value === "string" && value.trim()) {
          found = value
          break
        }
      }
      if (found) {
        break
      }
    }
    if (found) {
      parts.push(found)
    }
  }
  return parts.join("\n\n")
}

function reportSectionText(
  report: AnalyzeReportDetail,
  section: ReportSectionId
): string {
  if (section === "full") {
    return (
      collectMarkdown(report, ["complete_report"]) ||
      (typeof report.complete_report === "string" ? report.complete_report : "")
    )
  }
  if (section === "summary") {
    const decision = report.decision || report.meta?.decision || ""
    const summary = collectMarkdown(report, ["summary"])
    return [decision ? `决策：${decision}` : "", summary]
      .filter(Boolean)
      .join("\n\n")
  }
  if (section === "research") {
    return collectMarkdown(report, ["research", "bull", "bear", "manager"])
  }
  if (section === "trading") {
    return collectMarkdown(report, ["trading", "trader"])
  }
  if (section === "risk") {
    return collectMarkdown(report, [
      "risk",
      "aggressive",
      "conservative",
      "neutral",
    ])
  }
  if (section === "portfolio") {
    return collectMarkdown(report, ["portfolio", "decision.md", "5_portfolio"])
  }
  return collectMarkdown(report, [section])
}

export function AnalyzePage() {
  const { trackJob, jobs } = useJobs()
  const [searchParams, setSearchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
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

  const [hasRunning, setHasRunning] = useState(false)
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
  const unwatchRef = useRef<(() => void) | null>(null)
  const skipLogsRef = useRef(0)
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

  function stopWatch() {
    unwatchRef.current?.()
    unwatchRef.current = null
  }

  function attachJob(next: Job, existingLogCount = 0) {
    stopWatch()
    setJob(next)
    skipLogsRef.current = existingLogCount
    if (!isOpenJob(next.status)) {
      return
    }
    unwatchRef.current = watchJob(
      next.id,
      (line) => {
        if (skipLogsRef.current > 0) {
          skipLogsRef.current -= 1
          return
        }
        setLogs((prev) => [...prev, line])
      },
      (done) => {
        setJob(done)
        if (done.log?.length) {
          setLogs(done.log)
        }
        if (!isOpenJob(done.status)) {
          void listJobs().then((jobs) => {
            setHasRunning(jobs.some((item) => isOpenJob(item.status)))
          })
        }
        if (done.status === "succeeded") {
          const reportCode = pickJobString(done, "code")
          const reportDate = pickJobString(done, "date")
          const runId = pickJobString(done, "run_id")
          if (reportCode && reportDate) {
            void loadReport(reportCode, reportDate, runId ?? undefined)
            void loadReports(
              poolIdRef.current,
              filterByCodeRef.current ? reportCode : undefined
            )
          }
        }
      },
      (message) => {
        setError(message)
      }
    )
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
    setError(null)
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
      setError(err instanceof Error ? err.message : "读取报告失败")
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [nextSettings, listing, jobs] = await Promise.all([
          querySettings(),
          queryPools(),
          listJobs(),
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
        setHasRunning(jobs.some((item) => item.status === "running"))
        const urlCode = searchParams.get("code")
        const urlDate = searchParams.get("date")
        const urlRun = searchParams.get("run")
        if (urlCode) {
          setFilterByCode(true)
        }
        const preferredPool =
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
        const open = pickOpenAnalyzeJob(jobs)
        if (open) {
          const full = await getJob(open.id)
          if (cancelled) {
            return
          }
          setLogs(full.log ?? [])
          attachJob(full, full.log?.length ?? 0)
        }
        setError(null)
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
      stopWatch()
    }
    // First paint only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
      setError(err instanceof Error ? err.message : "加载股票池失败")
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
        setError(err instanceof Error ? err.message : "加载报告失败")
      }
    }
  }

  async function onToggleFilter(checked: boolean) {
    setFilterByCode(checked)
    try {
      await loadReports(poolId, checked ? code : undefined)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载报告失败")
    }
  }

  async function onSubmit() {
    if (!canSubmit) {
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const next = await submitAnalyzeRun({
        pool: poolId,
        code,
        date,
        analysts,
      })
      setLogs(next.log ?? [])
      attachJob(next, next.log?.length ?? 0)
      trackJob(next)
      const jobs = await listJobs()
      setHasRunning(
        jobs.some((item) => item.status === "running" || item.id === next.id)
      )
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "提交失败")
    } finally {
      setSubmitting(false)
    }
  }

  const decision =
    job && job.status === "succeeded" ? pickJobString(job, "decision") : null
  const openedText = opened ? reportSectionText(opened, section) : ""

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>分析页出错</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}
      <Alert>
        <InfoIcon />
        <AlertTitle>行情来源</AlertTitle>
        <AlertDescription>
          第 1 期行情来自 Yahoo，不是本地 market.db；A
          股覆盖一般，价格可能和股票池里的日线不一致。
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>发起分析</CardTitle>
          <CardDescription>
            从当前股票池挑一只票，选交易日再跑。一次完整图可能需要十几分钟。
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && settings === null ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : (
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="analyze-pool">股票池</FieldLabel>
                <Select
                  items={poolItems}
                  value={poolId || null}
                  onValueChange={(value) => {
                    void onSelectPool(typeof value === "string" ? value : null)
                  }}
                >
                  <SelectTrigger id="analyze-pool" className="min-w-56">
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
              </Field>
              <Field>
                <FieldLabel htmlFor="analyze-code">股票</FieldLabel>
                <div className="flex flex-wrap items-center gap-3">
                  <Select
                    items={memberItems}
                    value={code || null}
                    onValueChange={(value) => {
                      void onSelectCode(
                        typeof value === "string" ? value : null
                      )
                    }}
                  >
                    <SelectTrigger id="analyze-code" className="min-w-56">
                      <SelectValue placeholder="选择股票" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {memberItems.map((item) => (
                          <SelectItem key={item.value} value={item.value}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  {code ? <TickerLink code={code} /> : null}
                </div>
                {selectedMember?.last_bar ? (
                  <FieldDescription>
                    库里最新日线 {selectedMember.last_bar}。第 1
                    期不强制必须是交易日。
                  </FieldDescription>
                ) : (
                  <FieldDescription>
                    没有日线时，请手动填日期。
                  </FieldDescription>
                )}
              </Field>
              <Field>
                <FieldLabel htmlFor="analyze-date">交易日</FieldLabel>
                <Input
                  id="analyze-date"
                  type="date"
                  value={date}
                  className="max-w-48"
                  onChange={(event) => setDate(event.target.value)}
                />
              </Field>
              <Field>
                <FieldTitle id="analyze-analysts">分析师</FieldTitle>
                <ToggleGroup
                  aria-labelledby="analyze-analysts"
                  multiple
                  value={analysts}
                  onValueChange={(next) => {
                    const valid = next.filter(isAnalyst)
                    if (valid.length > 0) {
                      setAnalysts(valid)
                    }
                  }}
                  variant="outline"
                  spacing={0}
                >
                  {ANALYST_OPTIONS.map((item) => (
                    <ToggleGroupItem key={item.id} value={item.id}>
                      {item.label}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                <FieldDescription>
                  默认跟系统设置。情绪分析师依赖 Reddit / StockTwits，A
                  股几乎没用。
                </FieldDescription>
              </Field>
              {needsKey || needsBackend || needsModels ? (
                <FieldDescription>
                  {needsKey
                    ? "还没有 API 密钥，"
                    : needsBackend
                      ? "OpenAI 兼容端还没有接口地址，"
                      : "还没有填写模型名，"}
                  请先到 <Link to="/settings">系统设置</Link> 配置。Ollama
                  和本地兼容端可以不填密钥。
                </FieldDescription>
              ) : null}
              {hasRunning ? (
                <FieldDescription>当前有任务在跑，会排队。</FieldDescription>
              ) : null}
            </FieldGroup>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap items-center gap-3">
          <Button disabled={!canSubmit} onClick={() => void onSubmit()}>
            {submitting ? <Spinner data-icon="inline-start" /> : null}
            开始分析
          </Button>
          <span className="text-sm text-muted-foreground">
            可能需要十几分钟。
          </span>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>本次运行</CardTitle>
          <CardDescription>
            {job
              ? [job.id, jobQueuedHint(jobs, job)].filter(Boolean).join(" · ")
              : "提交后会在这里跟日志。刷新页面会接上还没结束的 analyze.run。"}
          </CardDescription>
          {job ? (
            <CardAction>
              <Badge variant={jobStatusVariant(job.status)}>
                {jobStatusLabel(job.status)}
              </Badge>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          {job ? (
            <div className="flex flex-col gap-3">
              <ScrollArea className="h-72 rounded-lg border">
                <pre className="p-3 font-mono text-sm whitespace-pre-wrap">
                  {logs.length > 0 ? logs.join("\n") : "还没有日志。"}
                </pre>
                <div ref={logEndRef} />
              </ScrollArea>
              {job.status === "failed" && job.error ? (
                <Alert variant="destructive">
                  <CircleAlertIcon />
                  <AlertTitle>任务失败</AlertTitle>
                  <AlertDescription>{job.error}</AlertDescription>
                </Alert>
              ) : null}
              {job.status === "succeeded" ? (
                <div className="flex flex-col gap-2">
                  <CardTitle>{decision || "已完成"}</CardTitle>
                  <FieldDescription>
                    决策来自这次运行。完整分段在下面的历史报告里。
                  </FieldDescription>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-fit"
                    onClick={() => {
                      const reportCode = pickJobString(job, "code")
                      const reportDate = pickJobString(job, "date")
                      const runId = pickJobString(job, "run_id")
                      if (reportCode && reportDate) {
                        void loadReport(
                          reportCode,
                          reportDate,
                          runId ?? undefined
                        )
                      }
                      reportCardRef.current?.scrollIntoView({ block: "start" })
                    }}
                  >
                    查看报告
                  </Button>
                </div>
              ) : null}
            </div>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileTextIcon />
                </EmptyMedia>
                <EmptyTitle>还没有正在看的任务</EmptyTitle>
                <EmptyDescription>
                  点「开始分析」之后，日志会出现在这里。
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
      </Card>

      <div ref={reportCardRef}>
        <Card>
          <CardHeader>
            <CardTitle>历史报告</CardTitle>
            <CardDescription>
              报告写在磁盘上。重启 core 后任务列表会空，这里还在。
            </CardDescription>
            <CardAction>
              <Field orientation="horizontal">
                <FieldLabel htmlFor="filter-code">只看当前股票</FieldLabel>
                <Switch
                  id="filter-code"
                  checked={filterByCode}
                  onCheckedChange={(checked) => {
                    void onToggleFilter(checked)
                  }}
                />
              </Field>
            </CardAction>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              {reportsLoading && reports.length === 0 ? (
                <div className="flex flex-col gap-2">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : reports.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>代码</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>日期</TableHead>
                      <TableHead>决策</TableHead>
                      <TableHead>时间</TableHead>
                      <TableHead className="w-20">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reports.map((item) => (
                      <TableRow
                        key={`${item.code}-${item.date}-${item.run_id}`}
                      >
                        <TableCell className="font-mono">
                          <TickerLink code={item.code} />
                        </TableCell>
                        <TableCell>{item.name || "—"}</TableCell>
                        <TableCell className="font-mono">{item.date}</TableCell>
                        <TableCell>{item.decision || "—"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatJobDateTime(item.created_at)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => {
                              void loadReport(item.code, item.date, item.run_id)
                            }}
                          >
                            打开
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Empty>
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <FileTextIcon />
                    </EmptyMedia>
                    <EmptyTitle>还没有报告</EmptyTitle>
                    <EmptyDescription>
                      跑完一次分析后，这里会出现决策和分段正文。
                    </EmptyDescription>
                  </EmptyHeader>
                  <EmptyContent>
                    <Button
                      size="sm"
                      disabled={!canSubmit}
                      onClick={() => void onSubmit()}
                    >
                      开始分析
                    </Button>
                  </EmptyContent>
                </Empty>
              )}

              {reportLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : opened ? (
                <div className="flex flex-col gap-3">
                  <FieldDescription className="flex flex-wrap items-center gap-x-2">
                    <TickerLink code={opened.code} />
                    <span>
                      {opened.name || opened.meta?.name || ""} · {opened.date} ·{" "}
                      {opened.decision || opened.meta?.decision || "—"}
                    </span>
                  </FieldDescription>
                  <Tabs
                    value={section}
                    onValueChange={(value) => {
                      if (REPORT_SECTIONS.some((item) => item.id === value)) {
                        setSection(value as ReportSectionId)
                      }
                    }}
                  >
                    <TabsList
                      variant="line"
                      className="h-auto w-full flex-wrap justify-start"
                    >
                      {REPORT_SECTIONS.map((item) => (
                        <TabsTrigger
                          key={item.id}
                          value={item.id}
                          className="flex-none"
                        >
                          {item.label}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    {REPORT_SECTIONS.map((item) => (
                      <TabsContent key={item.id} value={item.id}>
                        <pre className="text-sm whitespace-pre-wrap">
                          {item.id === section
                            ? openedText || "这一段没有内容。"
                            : ""}
                        </pre>
                      </TabsContent>
                    ))}
                  </Tabs>
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <p className="text-sm text-muted-foreground">研究工具，不是投资建议。</p>
    </div>
  )
}
