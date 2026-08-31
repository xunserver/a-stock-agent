import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { QlibRun } from "@/lib/api"
import { formatJobDateTime } from "@/lib/jobs"
import { cn } from "@/lib/utils"

export function RunHistoryPanel({
  runs,
  selectedRun,
  onSelect,
}: {
  runs: QlibRun[]
  selectedRun: QlibRun | null
  onSelect: (id: string) => void
}) {
  if (!runs.length) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>运行记录</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 p-2">
        {runs.map((run) => (
          <button
            key={run.run_id}
            type="button"
            className={cn(
              "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
              run.run_id === selectedRun?.run_id
                ? "bg-accent text-accent-foreground"
                : "hover:bg-muted/60"
            )}
            onClick={() => onSelect(run.run_id)}
          >
            <span className="font-medium">{run.as_of}</span>
            <span className="text-xs text-muted-foreground">
              {formatJobDateTime(run.created_at)}
              {run.candidate_count != null
                ? ` · ${run.candidate_count} 只`
                : ""}
            </span>
          </button>
        ))}
      </CardContent>
    </Card>
  )
}
