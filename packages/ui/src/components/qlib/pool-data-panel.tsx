import { DatabaseIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { Job, QlibOverview } from "@/lib/api"
import { formatJobDateTime } from "@/lib/jobs"

export function PoolDataPanel({
  overview,
  preparing,
  openPoolJob,
  openDumpJob,
  onPrepare,
}: {
  overview: QlibOverview
  preparing: boolean
  openPoolJob: Job | null
  openDumpJob: Job | null
  onPrepare: () => void
}) {
  const range =
    overview.data.calendar_first && overview.data.calendar_last
      ? `${overview.data.calendar_first} ~ ${overview.data.calendar_last}`
      : "尚未准备"
  return (
    <Card>
      <CardHeader>
        <CardTitle>池数据</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Row label="选股范围" value={`池成员 ${overview.pool.active} 只`} />
        <Row label="已准备标的" value={`${overview.data.symbol_count} 只`} />
        <Row label="行情区间" value={range} />
        <Row
          label="最近准备"
          value={
            overview.data.prepared_at
              ? formatJobDateTime(overview.data.prepared_at)
              : "—"
          }
        />
        <Row
          label="最近运行"
          value={overview.latest_run?.as_of ?? "尚未运行"}
        />
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full"
          disabled={preparing || Boolean(openPoolJob)}
          onClick={onPrepare}
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
  )
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  )
}
