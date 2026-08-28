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
import { Spinner } from "@/components/ui/spinner"
import type { Job } from "@/lib/api"
import { jobDisplayName } from "@/lib/jobs"

const DIALOG_Z = "z-[70]"

export function JobCancelDialog({
  job,
  busy,
  error,
  onOpenChange,
  onConfirm,
}: {
  job: Job | null
  busy: boolean
  error: string | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}) {
  const name = job ? jobDisplayName(job) : "任务"
  return (
    <AlertDialog
      open={job !== null}
      onOpenChange={(open) => {
        if (busy) {
          return
        }
        onOpenChange(open)
      }}
    >
      <AlertDialogContent className={DIALOG_Z} overlayClassName={DIALOG_Z}>
        <AlertDialogHeader>
          <AlertDialogTitle>取消「{name}」？</AlertDialogTitle>
          <AlertDialogDescription>
            任务会停掉，已经做完的部分不会回滚。确认后不能撤销。
            {error ? (
              <span className="mt-2 block text-destructive">{error}</span>
            ) : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>返回</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={busy}
            onClick={(event) => {
              event.preventDefault()
              onConfirm()
            }}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            确认取消
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
