import { StockDetailPanel } from "@/components/stock-detail-panel"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"

export function StockDetailDialog({
  code,
  onOpenChange,
}: {
  code: string | null
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={code !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] min-w-0 overflow-x-hidden overflow-y-auto sm:max-w-6xl">
        <DialogTitle className="sr-only">股票详情</DialogTitle>
        <DialogDescription className="sr-only">
          行情、资料、日 K 线与相关新闻
        </DialogDescription>
        <StockDetailPanel code={code} headerClassName="pr-8" />
      </DialogContent>
    </Dialog>
  )
}
