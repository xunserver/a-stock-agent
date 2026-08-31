import { useMemo, useState } from "react"

import { CandidateTable } from "@/components/qlib/candidate-table"
import { PoolDataPanel } from "@/components/qlib/pool-data-panel"
import { RunHistoryPanel } from "@/components/qlib/run-history-panel"
import { topOptionsFor } from "@/components/qlib/helpers"
import { useQlibPage } from "@/components/qlib/use-qlib-page"
import { WorkflowPanel } from "@/components/qlib/workflow-panel"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

export function QlibPage() {
  const page = useQlibPage()
  const [displayTop, setDisplayTop] = useState(10)
  const candidates = page.selectedRun?.candidates ?? []
  const topOptions = useMemo(
    () => topOptionsFor(candidates.length),
    [candidates.length]
  )
  const visibleTop = topOptions.some(
    (item) => Number(item.value) === displayTop
  )
    ? displayTop
    : Number(topOptions.at(-1)?.value ?? displayTop)
  return (
    <div className="flex flex-col gap-4">
      <QlibHeader
        poolId={page.poolId}
        poolItems={page.poolItems}
        onSelect={page.onSelectPool}
      />
      {page.loading || !page.workflow || !page.overview ? (
        <QlibLoading />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <WorkflowPanel
            overview={page.overview}
            workflow={page.workflow}
            submitting={page.submitting}
            openPoolJob={page.openPoolJob}
            openRunJob={page.openRunJob}
            onPatch={page.patchWorkflow}
            onRun={() => void page.onRun()}
          />
          <PoolDataPanel
            overview={page.overview}
            preparing={page.preparing}
            openPoolJob={page.openPoolJob}
            openDumpJob={page.openDumpJob}
            onPrepare={() => void page.onPrepare()}
          />
        </div>
      )}
      <RunHistoryPanel
        runs={page.runs}
        selectedRun={page.selectedRun}
        onSelect={(id) => void page.onSelectRun(id)}
      />
      <CandidateTable
        poolId={page.poolId}
        selectedRun={page.selectedRun}
        candidates={candidates}
        topOptions={topOptions}
        visibleTop={visibleTop}
        workflow={page.workflow}
        overview={page.overview}
        submitting={page.submitting}
        openPoolJob={page.openPoolJob}
        onDisplayTop={setDisplayTop}
        onRun={() => void page.onRun()}
      />
    </div>
  )
}

function QlibHeader({
  poolId,
  poolItems,
  onSelect,
}: {
  poolId: string
  poolItems: { value: string; label: string }[]
  onSelect: (value: string | null) => Promise<void>
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h1 className="text-2xl font-semibold">量化选股</h1>
      <Select
        items={poolItems}
        value={poolId || null}
        onValueChange={(value) =>
          void onSelect(typeof value === "string" ? value : null)
        }
      >
        <SelectTrigger className="min-w-56">
          <SelectValue placeholder="选择股票池" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {poolItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
function QlibLoading() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Skeleton className="h-72 lg:col-span-2" />
      <Skeleton className="h-72" />
    </div>
  )
}
