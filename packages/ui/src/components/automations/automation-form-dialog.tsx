import { useEffect, useMemo, useState, type FormEvent } from "react"
import { CircleAlertIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type {
  Automation,
  AutomationCommandDefinition,
  AutomationInput,
} from "@/lib/api"
import { createAutomation, updateAutomation } from "@/lib/api"

import { AutomationFormFields } from "./automation-form-fields"
import { automationDraft, blankDraft } from "./helpers"

type Props = {
  value: Automation | "new" | null
  catalog: AutomationCommandDefinition[]
  onClose: () => void
  onSaved: () => Promise<void>
}

export function AutomationFormDialog({
  value,
  catalog,
  onClose,
  onSaved,
}: Props) {
  const [draft, setDraft] = useState(() => blankDraft(catalog))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!value) return
    setDraft(value === "new" ? blankDraft(catalog) : automationDraft(value))
    setError(null)
  }, [value, catalog])
  const definition = useMemo(
    () => catalog.find((item) => item.type === draft.command.type),
    [catalog, draft.command.type]
  )
  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const command = Object.fromEntries(
      Object.entries(draft.command).filter(
        ([key, item]) => key === "type" || item.trim() !== ""
      )
    )
    const payload: AutomationInput = { ...draft, command }
    try {
      if (value === "new") await createAutomation(payload)
      else if (value) await updateAutomation(value.id, payload)
      await onSaved()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }
  return (
    <Dialog open={value !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>
              {value === "new" ? "新建自动任务" : "编辑自动任务"}
            </DialogTitle>
            <DialogDescription>
              自动任务到点后会提交普通 Job，每一次执行和日志都会永久保留。
            </DialogDescription>
          </DialogHeader>
          {error ? (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <AutomationFormFields
            catalog={catalog}
            definition={definition}
            draft={draft}
            setDraft={setDraft}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
