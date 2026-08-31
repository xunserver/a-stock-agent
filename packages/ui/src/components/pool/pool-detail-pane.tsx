import { StockDetailPanel } from "@/components/stock-detail-panel"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function PoolDetailPane({
  loading,
  membersPending,
  selectedCode,
}: {
  loading: boolean
  membersPending: boolean
  selectedCode: string | null
}) {
  return (
    <Card className="h-full min-h-0 min-w-0">
      <CardContent className="min-h-0 flex-1 overflow-y-auto">
        {loading && membersPending ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-[28rem] w-full" />
          </div>
        ) : (
          <StockDetailPanel code={selectedCode} />
        )}
      </CardContent>
    </Card>
  )
}
