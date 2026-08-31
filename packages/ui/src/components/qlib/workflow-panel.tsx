import { SparklesIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import type { Job, QlibOverview, QlibWorkflow } from "@/lib/api"

import { WORKFLOW_OPTIONS } from "./helpers"

type Props = {
  overview: QlibOverview
  workflow: QlibWorkflow
  submitting: boolean
  openPoolJob: Job | null
  openRunJob: Job | null
  onPatch: (patch: Partial<QlibWorkflow>) => void
  onRun: () => void
}

export function WorkflowPanel({
  overview,
  workflow,
  submitting,
  openPoolJob,
  openRunJob,
  onPatch,
  onRun,
}: Props) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Workflow</CardTitle>
        <CardAction>
          <Badge variant={overview.data.ready ? "default" : "outline"}>
            {overview.data.ready ? "数据就绪" : "请先准备数据"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <FieldGroup className="grid md:grid-cols-2">
          <WorkflowConfig
            workflow={workflow}
            active={overview.pool.active}
            onPatch={onPatch}
          />
        </FieldGroup>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Button
          disabled={submitting || Boolean(openPoolJob) || !overview.data.ready}
          onClick={onRun}
        >
          {submitting || openRunJob ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <SparklesIcon data-icon="inline-start" />
          )}
          {openRunJob
            ? "选股运行中"
            : overview.data.ready
              ? "运行选股"
              : "请先准备数据"}
        </Button>
      </CardFooter>
    </Card>
  )
}

function WorkflowConfig({
  workflow,
  active,
  onPatch,
}: {
  workflow: QlibWorkflow
  active: number
  onPatch: (patch: Partial<QlibWorkflow>) => void
}) {
  return (
    <>
      <Field>
        <FieldLabel>配置模板</FieldLabel>
        <Select
          items={WORKFLOW_OPTIONS}
          value={workflow.config}
          onValueChange={(value) => {
            if (typeof value === "string") onPatch({ config: value })
          }}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {WORKFLOW_OPTIONS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
      <Field>
        <FieldLabel htmlFor="qlib-benchmark">回测基准</FieldLabel>
        <Input
          id="qlib-benchmark"
          value={workflow.benchmark}
          onChange={(event) => onPatch({ benchmark: event.target.value })}
        />
      </Field>
      <NumberField
        id="qlib-topk"
        label="候选只数"
        value={workflow.topk}
        min={1}
        max={active}
        onChange={(topk) => onPatch({ topk })}
      />
      <NumberField
        id="qlib-drop"
        label="每期换出"
        value={workflow.n_drop}
        min={0}
        max={100}
        onChange={(n_drop) => onPatch({ n_drop })}
      />
      <NumberField
        id="qlib-account"
        label="回测本金"
        value={workflow.account}
        min={1}
        onChange={(account) => onPatch({ account })}
      />
      <OptionalTextField
        id="qlib-data-end"
        label="数据截止日"
        placeholder="YYYY-MM-DD，留空用最新"
        value={workflow.data_end ?? null}
        onChange={(data_end) => onPatch({ data_end })}
      />
      <OptionalTextField
        id="qlib-test-start"
        label="测试区间起始"
        placeholder="YYYY-MM-DD，留空用模板默认"
        value={workflow.test_start ?? null}
        onChange={(test_start) => onPatch({ test_start })}
      />
      <Field>
        <FieldLabel htmlFor="qlib-lr">学习率</FieldLabel>
        <Input
          id="qlib-lr"
          type="number"
          min={0.0001}
          max={1}
          step={0.01}
          placeholder="留空用模板默认"
          value={workflow.learning_rate ?? ""}
          onChange={(event) => {
            const raw = event.target.value.trim()
            onPatch({ learning_rate: raw ? Number(raw) : null })
          }}
        />
      </Field>
    </>
  )
}

function NumberField({
  id,
  label,
  value,
  min,
  max,
  onChange,
}: {
  id: string
  label: string
  value: number
  min: number
  max?: number
  onChange: (value: number) => void
}) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  )
}
function OptionalTextField({
  id,
  label,
  placeholder,
  value,
  onChange,
}: {
  id: string
  label: string
  placeholder: string
  value: string | null
  onChange: (value: string | null) => void
}) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        placeholder={placeholder}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value.trim() || null)}
      />
    </Field>
  )
}
