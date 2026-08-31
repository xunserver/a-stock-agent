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

type RemoveStockDialogProps = {
  code: string | null
  busy: boolean
  onOpenChange: (open: boolean) => void
  onRemove: (code: string) => void
}

export function RemoveStockDialog({
  code,
  busy,
  onOpenChange,
  onRemove,
}: RemoveStockDialogProps) {
  return (
    <AlertDialog open={code !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            从系统移除 {code ? tickerFromCode(code) : ""}？
          </AlertDialogTitle>
          <AlertDialogDescription>
            只从股票目录拿掉，不删日线。若还在股票池里，这里会拒绝。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={busy || !code}
            onClick={(event) => {
              event.preventDefault()
              if (code) onRemove(code)
            }}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}移除
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
