import { useEffect, useState } from "react"
import { CircleAlertIcon } from "lucide-react"

import { AutomationDetailPageContent } from "@/components/automations/automation-detail-page"
import { AutomationFormDialog } from "@/components/automations/automation-form-dialog"
import { AutomationListCard } from "@/components/automations/automation-list-card"
import { useJobs } from "@/components/job-provider"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  getAutomationCatalog,
  listAutomations,
  runAutomation,
  updateAutomation,
  type Automation,
  type AutomationCommandDefinition,
} from "@/lib/api"

export function AutomationsPage() {
  const [items, setItems] = useState<Automation[]>([])
  const [catalog, setCatalog] = useState<AutomationCommandDefinition[]>([])
  const [editing, setEditing] = useState<Automation | "new" | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { trackJob } = useJobs()
  async function refresh() {
    setItems(await listAutomations())
    setError(null)
  }
  useEffect(() => {
    let cancelled = false
    void Promise.all([listAutomations(), getAutomationCatalog()])
      .then(([next, definitions]) => {
        if (!cancelled) {
          setItems(next)
          setCatalog(definitions)
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(
            reason instanceof Error ? reason.message : "加载自动任务失败"
          )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])
  async function onToggle(item: Automation) {
    try {
      await updateAutomation(item.id, { enabled: !item.enabled })
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "更新失败")
    }
  }
  async function onRun(item: Automation) {
    try {
      trackJob(await runAutomation(item.id))
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "提交失败")
    }
  }
  return (
    <div className="flex flex-col gap-4">
      {error ? <AutomationError error={error} /> : null}
      <AutomationListCard
        items={items}
        loading={loading}
        onEdit={setEditing}
        onRun={(item) => void onRun(item)}
        onToggle={(item) => void onToggle(item)}
      />
      <AutomationFormDialog
        value={editing}
        catalog={catalog}
        onClose={() => setEditing(null)}
        onSaved={async () => {
          setEditing(null)
          await refresh()
        }}
      />
    </div>
  )
}

export function AutomationDetailPage() {
  return <AutomationDetailPageContent />
}
function AutomationError({ error }: { error: string }) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertTitle>自动任务操作失败</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  )
}
