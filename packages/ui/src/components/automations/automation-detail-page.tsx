import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router"
import { ArchiveIcon, CircleAlertIcon } from "lucide-react"

import { AutomationSummary } from "@/components/automations/automation-detail-panels"
import { AutomationFormDialog } from "@/components/automations/automation-form-dialog"
import { AutomationRunHistory } from "@/components/automations/automation-run-history"
import { useJobs } from "@/components/job-provider"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  archiveAutomation,
  getAutomation,
  getAutomationCatalog,
  listAutomationRuns,
  runAutomation,
  type Automation,
  type AutomationCommandDefinition,
  type Job,
} from "@/lib/api"

export function AutomationDetailPageContent() {
  const { automationId = "" } = useParams()
  const navigate = useNavigate()
  const { jobs, openJob, trackJob } = useJobs()
  const [item, setItem] = useState<Automation | null>(null)
  const [runs, setRuns] = useState<Job[]>([])
  const [count, setCount] = useState(0)
  const [date, setDate] = useState("")
  const [editing, setEditing] = useState<Automation | null>(null)
  const [catalog, setCatalog] = useState<AutomationCommandDefinition[]>([])
  const [error, setError] = useState<string | null>(null)
  const mergedRuns = useMemo(
    () => runs.map((run) => jobs.find((job) => job.id === run.id) ?? run),
    [runs, jobs]
  )
  async function refresh() {
    const [automation, history] = await Promise.all([
      getAutomation(automationId),
      listAutomationRuns(automationId, date || undefined),
    ])
    setItem(automation)
    setRuns(history.jobs)
    setCount(history.count)
    setError(null)
  }
  useEffect(() => {
    let cancelled = false
    void Promise.all([
      getAutomation(automationId),
      listAutomationRuns(automationId, date || undefined),
      getAutomationCatalog(),
    ])
      .then(([automation, history, definitions]) => {
        if (!cancelled) {
          setItem(automation)
          setRuns(history.jobs)
          setCount(history.count)
          setCatalog(definitions)
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "加载失败")
      })
    return () => {
      cancelled = true
    }
  }, [automationId, date])
  if (!item && !error) return <Skeleton className="h-72 w-full" />
  async function onRun() {
    try {
      trackJob(await runAutomation(automationId))
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "提交失败")
    }
  }
  async function onArchive() {
    if (!window.confirm("归档后任务不会再运行，但历史记录会永久保留。继续吗？"))
      return
    try {
      await archiveAutomation(automationId)
      navigate("/automations")
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "归档失败")
    }
  }
  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>无法读取自动任务</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {item ? (
        <>
          <AutomationSummary
            item={item}
            onEdit={() => setEditing(item)}
            onRun={() => void onRun()}
          />
          <AutomationRunHistory
            count={count}
            date={date}
            runs={mergedRuns}
            onDateChange={setDate}
            onOpen={openJob}
          />
          <div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void onArchive()}
            >
              <ArchiveIcon data-icon="inline-start" />
              归档自动任务
            </Button>
          </div>
          <AutomationFormDialog
            value={editing}
            catalog={catalog}
            onClose={() => setEditing(null)}
            onSaved={async () => {
              setEditing(null)
              await refresh()
            }}
          />
        </>
      ) : null}
    </div>
  )
}
