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
import { tickerFromCode } from "@/lib/ticker"

export function PoolConfirmDialogs({
  poolId,
  busy,
  deleteOpen,
  removeCodes,
  onDeleteOpenChange,
  onRemoveCodesChange,
  onDelete,
  onRemove,
}: {
  poolId: string | null
  busy: boolean
  deleteOpen: boolean
  removeCodes: string[] | null
  onDeleteOpenChange: (open: boolean) => void
  onRemoveCodesChange: (codes: string[] | null) => void
  onDelete: () => void
  onRemove: (codes: string[]) => void
}) {
  return (
    <>
      <AlertDialog open={deleteOpen} onOpenChange={onDeleteOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除股票池 {poolId}？</AlertDialogTitle>
            <AlertDialogDescription>
              只删池和成员关系，已入库的日线还在。至少保留一个股票池。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={busy}
              onClick={(event) => {
                event.preventDefault()
                onDelete()
              }}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog
        open={removeCodes !== null}
        onOpenChange={(open) => {
          if (!open) onRemoveCodesChange(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {removeCodes && removeCodes.length === 1
                ? `移出 ${tickerFromCode(removeCodes[0])}？`
                : `移出 ${removeCodes?.length ?? 0} 只股票？`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              从当前池拿掉
              {removeCodes && removeCodes.length === 1 ? "这只票" : "这些票"}
              ，不删日线。以后还可以再加回来。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy || !removeCodes || removeCodes.length === 0}
              onClick={(event) => {
                event.preventDefault()
                if (removeCodes?.length) onRemove(removeCodes)
              }}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}移出
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
