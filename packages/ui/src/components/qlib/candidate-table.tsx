import { Link } from "react-router"
import { BrainIcon, SparklesIcon } from "lucide-react"

import { TickerLink } from "@/components/ticker-link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyContent,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type {
  Job,
  QlibCandidate,
  QlibOverview,
  QlibRun,
  QlibWorkflow,
} from "@/lib/api"
import { changeTextClass } from "@/lib/change"
import { fmtPct } from "@/lib/financial-metrics"
import { cn } from "@/lib/utils"

import { formatScore } from "./helpers"

type Option = { value: string; label: string }
type Props = {
  poolId: string
  selectedRun: QlibRun | null
  candidates: QlibCandidate[]
  topOptions: Option[]
  visibleTop: number
  workflow: QlibWorkflow | null
  overview: QlibOverview | null
  submitting: boolean
  openPoolJob: Job | null
  onDisplayTop: (value: number) => void
  onRun: () => void
}

export function CandidateTable({
  poolId,
  selectedRun,
  candidates,
  topOptions,
  visibleTop,
  workflow,
  overview,
  submitting,
  openPoolJob,
  onDisplayTop,
  onRun,
}: Props) {
  const nextDay = selectedRun?.next_trade_date
    ? `次日涨跌 (${selectedRun.next_trade_date.slice(5)})`
    : "次日涨跌"
  const enabled =
    !workflow || submitting || Boolean(openPoolJob) || !overview?.data.ready
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {selectedRun ? `${selectedRun.as_of} 候选结果` : "候选结果"}
        </CardTitle>
        {candidates.length ? (
          <CardAction>
            <Select
              items={topOptions}
              value={String(visibleTop)}
              onValueChange={(value) => {
                if (typeof value === "string") onDisplayTop(Number(value))
              }}
            >
              <SelectTrigger className="min-w-28">
                <SelectValue placeholder="Top" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {topOptions.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        {candidates.length ? (
          <CandidatesTable
            candidates={candidates.slice(0, visibleTop)}
            poolId={poolId}
            nextDay={nextDay}
          />
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <SparklesIcon />
              </EmptyMedia>
              <EmptyTitle>还没有候选结果</EmptyTitle>
            </EmptyHeader>
            <EmptyContent>
              <Button disabled={enabled} onClick={onRun}>
                运行选股
              </Button>
            </EmptyContent>
          </Empty>
        )}
      </CardContent>
    </Card>
  )
}

function CandidatesTable({
  candidates,
  poolId,
  nextDay,
}: {
  candidates: QlibCandidate[]
  poolId: string
  nextDay: string
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">排名</TableHead>
          <TableHead>股票</TableHead>
          <TableHead>Qlib Symbol</TableHead>
          <TableHead className="text-right">Score</TableHead>
          <TableHead className="text-right">{nextDay}</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {candidates.map((candidate) => (
          <TableRow key={candidate.code}>
            <TableCell>{candidate.rank}</TableCell>
            <TableCell>
              <TickerLink code={candidate.code}>
                {candidate.name
                  ? `${candidate.code} ${candidate.name}`
                  : candidate.code}
              </TickerLink>
            </TableCell>
            <TableCell>{candidate.symbol}</TableCell>
            <TableCell className="text-right font-mono">
              {formatScore(candidate.score)}
            </TableCell>
            <TableCell
              className={cn(
                "text-right font-mono tabular-nums",
                changeTextClass(candidate.next_day_pct_chg)
              )}
            >
              {fmtPct(candidate.next_day_pct_chg)}
            </TableCell>
            <TableCell className="text-right">
              <Button
                variant="ghost"
                size="sm"
                nativeButton={false}
                render={
                  <Link
                    to={`/analyze?pool=${encodeURIComponent(poolId)}&code=${candidate.code}`}
                  />
                }
              >
                <BrainIcon data-icon="inline-start" />
                分析
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
