import { Link } from "react-router"

import { ANALYST_OPTIONS, isAnalyst } from "@/components/analyze/analyze-model"
import { TickerLink } from "@/components/ticker-link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { AnalystKind, PoolMember } from "@/lib/api"

type SelectItemOption = { label: string; value: string }

type AnalyzeSetupCardProps = {
  loading: boolean
  poolItems: SelectItemOption[]
  memberItems: SelectItemOption[]
  poolId: string
  code: string
  date: string
  analysts: AnalystKind[]
  selectedMember: PoolMember | null
  needsKey: boolean
  needsBackend: boolean
  needsModels: boolean
  hasRunning: boolean
  canSubmit: boolean
  submitting: boolean
  onSelectPool: (value: string | null) => void
  onSelectCode: (value: string | null) => void
  onDateChange: (value: string) => void
  onAnalystsChange: (value: AnalystKind[]) => void
  onSubmit: () => void
}

/** Presentational form for choosing an analysis target and model roles. */
export function AnalyzeSetupCard({
  loading,
  poolItems,
  memberItems,
  poolId,
  code,
  date,
  analysts,
  selectedMember,
  needsKey,
  needsBackend,
  needsModels,
  hasRunning,
  canSubmit,
  submitting,
  onSelectPool,
  onSelectCode,
  onDateChange,
  onAnalystsChange,
  onSubmit,
}: AnalyzeSetupCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>发起分析</CardTitle>
        <CardDescription>
          从当前股票池挑一只票，选交易日再跑。一次完整图可能需要十几分钟。
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="analyze-pool">股票池</FieldLabel>
              <Select
                items={poolItems}
                value={poolId || null}
                onValueChange={(value) =>
                  onSelectPool(typeof value === "string" ? value : null)
                }
              >
                <SelectTrigger id="analyze-pool" className="min-w-56">
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
            </Field>
            <Field>
              <FieldLabel htmlFor="analyze-code">股票</FieldLabel>
              <div className="flex flex-wrap items-center gap-3">
                <Select
                  items={memberItems}
                  value={code || null}
                  onValueChange={(value) =>
                    onSelectCode(typeof value === "string" ? value : null)
                  }
                >
                  <SelectTrigger id="analyze-code" className="min-w-56">
                    <SelectValue placeholder="选择股票" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {memberItems.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {code ? <TickerLink code={code} /> : null}
              </div>
              <FieldDescription>
                {selectedMember?.last_bar
                  ? `库里最新日线 ${selectedMember.last_bar}。第 1 期不强制必须是交易日。`
                  : "没有日线时，请手动填日期。"}
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="analyze-date">交易日</FieldLabel>
              <Input
                id="analyze-date"
                type="date"
                value={date}
                className="max-w-48"
                onChange={(event) => onDateChange(event.target.value)}
              />
            </Field>
            <Field>
              <FieldTitle id="analyze-analysts">分析师</FieldTitle>
              <ToggleGroup
                aria-labelledby="analyze-analysts"
                multiple
                value={analysts}
                onValueChange={(next) => {
                  const valid = next.filter(isAnalyst)
                  if (valid.length > 0) onAnalystsChange(valid)
                }}
                variant="outline"
                spacing={0}
              >
                {ANALYST_OPTIONS.map((item) => (
                  <ToggleGroupItem key={item.id} value={item.id}>
                    {item.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <FieldDescription>
                默认跟系统设置。情绪分析师依赖 Reddit / StockTwits，A
                股几乎没用。
              </FieldDescription>
            </Field>
            {needsKey || needsBackend || needsModels ? (
              <FieldDescription>
                {needsKey
                  ? "还没有 API 密钥，"
                  : needsBackend
                    ? "OpenAI 兼容端还没有接口地址，"
                    : "还没有填写模型名，"}
                请先到 <Link to="/settings">系统设置</Link> 配置。Ollama
                和本地兼容端可以不填密钥。
              </FieldDescription>
            ) : null}
            {hasRunning ? (
              <FieldDescription>当前有任务在跑，会排队。</FieldDescription>
            ) : null}
          </FieldGroup>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap items-center gap-3">
        <Button disabled={!canSubmit} onClick={onSubmit}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}开始分析
        </Button>
        <span className="text-sm text-muted-foreground">
          可能需要十几分钟。
        </span>
      </CardFooter>
    </Card>
  )
}
